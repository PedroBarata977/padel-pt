"""Recolhe tudo e escreve docs/data.json.

Uso:  python -m collector.main            (normal)
      python -m collector.main --verbose  (mostra cada pedido)
"""
import argparse
import json
import logging
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import draws, entrylist, fip, matchscorer
from .countries import TARGET
from .http import Client

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data.json"
CACHE = ROOT / "data" / "pdf_cache.json"  # PDFs já lidos (o URL muda a cada versão: v4, v13...)

log = logging.getLogger("padel")

DRAW_TYPES = {"MD": "Masculino · Quadro principal", "MQ": "Masculino · Qualificação",
              "WD": "Feminino · Quadro principal", "WQ": "Feminino · Qualificação"}
ENTRY_GENDERS = {"M": "Masculino", "W": "Feminino"}


def load_cache() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def collect_event(c: Client, ev: dict, cache: dict, today: date) -> dict:
    out = {**ev, "por_entries": [], "por_matches": [], "por_draws": [], "entry_lists": {},
           "draw_pdfs": {}, "warnings": []}
    page = c.get(ev["url"]).text
    info = fip.parse_event_page(page)
    out["registration_text"] = info["registration"]
    if not info["post_id"] or not info["nonce"]:
        out["warnings"].append("Página do evento sem postID/nonce — o site mudou?")
        return out

    # ---------- listas de inscritos (PDF)
    for g, label in ENTRY_GENDERS.items():
        try:
            r = fip.ajax_entry(c, info["post_id"], info["nonce"], g)
        except Exception as e:  # noqa: BLE001
            out["warnings"].append(f"Inscritos {label}: {e}")
            continue
        pdf = r.get("pdf") or ""
        out["entry_lists"][g] = {"pdf": pdf or None}
        if not pdf:
            continue
        if pdf not in cache:
            try:
                parsed = entrylist.parse_pdf(c.get(pdf).content)
                cache[pdf] = {"updated": parsed["updated"], "n_teams": len(parsed["teams"]),
                              "por": entrylist.teams_with(parsed, TARGET)}
            except Exception as e:  # noqa: BLE001
                out["warnings"].append(f"PDF inscritos {label} ilegível: {e}")
                continue
        cached = cache[pdf]
        out["entry_lists"][g].update(updated=cached["updated"], n_teams=cached["n_teams"])
        if cached["n_teams"] == 0:
            out["warnings"].append(f"PDF inscritos {label} lido mas sem equipas — layout mudou?")
        for t in cached["por"]:
            out["por_entries"].append({**t, "gender": g})

    # ---------- quadros (só perto/durante o torneio)
    start = date.fromisoformat(ev["start"])
    if ev["status"] == "live" or (start - today).days <= 3:
        for dt, label in DRAW_TYPES.items():
            try:
                r = fip.ajax_draw(c, info["post_id"], info["nonce"], dt)
            except Exception as e:  # noqa: BLE001
                out["warnings"].append(f"Quadro {label}: {e}")
                continue
            if r.get("pdf"):
                out["draw_pdfs"][dt] = r["pdf"]
            if str(r.get("error")) == "200" and r.get("html"):
                for team in draws.team_path(draws.parse_draw(r["html"], qualy=dt.endswith("Q")), TARGET):
                    out["por_draws"].append({**team, "draw": dt, "draw_label": label})

    # ---------- ordem de jogo + resultados + live (MatchScorer)
    if info["oop"]:
        o = info["oop"]
        year = int(o["year"])
        days_dates: dict[int, str] = {}
        for day in range(1, o["totalday"] + 1):
            try:
                res = matchscorer.parse_oop(c.get(matchscorer.url(year, o["id"], day)).text, year)
            except Exception as e:  # noqa: BLE001
                out["warnings"].append(f"Ordem de jogo dia {day}: {e}")
                continue
            days_dates.update(res["days"])
            for m in res["matches"]:
                if matchscorer.has_nat(m, TARGET):
                    out["por_matches"].append({**m, "day": day, "date": days_dates.get(day),
                                               "local_time": res["local_time"]})
        for m in out["por_matches"]:
            m["date"] = m["date"] or days_dates.get(m["day"])
        out["matchscorer_id"] = f"FIP-{year}-{o['id']}"
    return out


def run(verbose: bool = False) -> dict:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(message)s")
    c = Client()
    today = datetime.now(timezone.utc).date()
    cache = load_cache()
    events, errors = [], []

    for key, path in fip.CALENDARS.items():
        for year in (today.year, today.year + 1):
            try:
                events += fip.parse_calendar(c.get(fip.BASE + path.format(year=year)).text)
            except Exception as e:  # noqa: BLE001
                if year == today.year:
                    errors.append(f"Calendário {key} {year}: {e}")

    # só torneios que ainda não acabaram (com 1 dia de margem) e até 60 dias à frente
    seen, upcoming = set(), []
    for ev in sorted(events, key=lambda e: e["start"]):
        end, start = date.fromisoformat(ev["end"]), date.fromisoformat(ev["start"])
        if ev["slug"] in seen or end < today - timedelta(days=1) or start > today + timedelta(days=60):
            continue
        seen.add(ev["slug"])
        upcoming.append(ev)
    log.info("%d torneios a acompanhar", len(upcoming))

    collected = []
    for ev in upcoming:
        log.info("→ %s (%s)", ev["name"], ev["status"])
        if ev["status"] == "registration_not_open":
            collected.append({**ev, "por_entries": [], "por_matches": [], "por_draws": [],
                              "entry_lists": {}, "warnings": []})
            continue
        try:
            collected.append(collect_event(c, ev, cache, today))
        except Exception as e:  # noqa: BLE001
            log.warning("  falhou: %s", e)
            if verbose:
                traceback.print_exc()
            collected.append({**ev, "por_entries": [], "por_matches": [], "por_draws": [],
                              "entry_lists": {}, "warnings": [f"Falha geral: {e}"]})

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": TARGET,
        "stats": {"requests": c.count, "blocked_403": c.blocked, "events": len(collected),
                  "errors": errors},
        "events": collected,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    # a cache só guarda PDFs ainda referidos, para não crescer para sempre
    live_pdfs = {v["pdf"] for e in collected for v in e.get("entry_lists", {}).values() if v.get("pdf")}
    CACHE.write_text(json.dumps({k: v for k, v in cache.items() if k in live_pdfs},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("Feito: %d pedidos, %d bloqueados (403).", c.count, c.blocked)
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    data = run(a.verbose)
    # falha o job (e o GitHub manda-te email) se não se conseguiu ler nada
    if not data["events"] or data["stats"]["blocked_403"] > data["stats"]["requests"] / 2:
        sys.exit(1)


if __name__ == "__main__":
    main()
