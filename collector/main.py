"""Recolhedor em duas partes.

  python -m collector.main fip    → corre no PC do Pedro (a FIP bloqueia servidores com Cloudflare).
                                    Lê calendário, inscritos (PDF), quadros e IDs MatchScorer.
                                    Escreve docs/fip.json (e envia-o para o GitHub com collector.publish).
  python -m collector.main live   → corre no GitHub Actions. Lê docs/fip.json + MatchScorer
                                    (ordem de jogo, resultados, live). Escreve docs/data.json.
  python -m collector.main all    → as duas seguidas (útil para testar no PC).
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
FIP_OUT = ROOT / "docs" / "fip.json"
CACHE = ROOT / "data" / "pdf_cache.json"  # PDFs já lidos (o URL muda a cada versão: v4, v13...)

log = logging.getLogger("padel")

DRAW_TYPES = {"MD": "Masculino · Quadro principal", "MQ": "Masculino · Qualificação",
              "WD": "Feminino · Quadro principal", "WQ": "Feminino · Qualificação"}
ENTRY_GENDERS = {"M": "Masculino", "W": "Feminino"}


def _now():
    return datetime.now(timezone.utc)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def empty_event(ev: dict, warning: str | None = None) -> dict:
    return {**ev, "por_entries": [], "por_matches": [], "por_draws": [], "entry_lists": {},
            "draw_pdfs": {}, "oop": None, "warnings": [warning] if warning else []}


# =============================================================== parte FIP (PC)

def collect_fip_event(c: Client, ev: dict, cache: dict, today: date) -> dict:
    out = empty_event(ev)
    page = c.get(ev["url"]).text
    info = fip.parse_event_page(page)
    out["registration_text"] = info["registration"]
    out["oop"] = info["oop"]
    if not info["post_id"] or not info["nonce"]:
        out["warnings"].append("Página do evento sem postID/nonce — o site mudou?")
        return out

    for g, label in ENTRY_GENDERS.items():
        try:
            r = fip.ajax_entry(c, info["post_id"], info["nonce"], g, referer=ev["url"])
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

    start = date.fromisoformat(ev["start"])
    if ev["status"] == "live" or (start - today).days <= 3:
        for dt, label in DRAW_TYPES.items():
            try:
                r = fip.ajax_draw(c, info["post_id"], info["nonce"], dt, referer=ev["url"])
            except Exception as e:  # noqa: BLE001
                out["warnings"].append(f"Quadro {label}: {e}")
                continue
            if r.get("pdf"):
                out["draw_pdfs"][dt] = r["pdf"]
            if str(r.get("error")) == "200" and r.get("html"):
                for team in draws.team_path(draws.parse_draw(r["html"], qualy=dt.endswith("Q")), TARGET):
                    out["por_draws"].append({**team, "draw": dt, "draw_label": label})
    return out


def run_fip(c: Client, today: date) -> dict:
    cache = load_json(CACHE, {})
    events, errors = [], []
    for key, path in fip.CALENDARS.items():
        for year in (today.year, today.year + 1):
            try:
                events += fip.parse_calendar(c.get(fip.BASE + path.format(year=year)).text)
            except Exception as e:  # noqa: BLE001
                if year == today.year:
                    errors.append(f"Calendário {key} {year}: {e}")

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
            collected.append(empty_event(ev))
            continue
        try:
            collected.append(collect_fip_event(c, ev, cache, today))
        except Exception as e:  # noqa: BLE001
            log.warning("  falhou: %s", e)
            log.debug(traceback.format_exc())
            collected.append(empty_event(ev, f"Falha geral: {e}"))

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    live_pdfs = {v["pdf"] for e in collected for v in e["entry_lists"].values() if v.get("pdf")}
    CACHE.write_text(json.dumps({k: v for k, v in cache.items() if k in live_pdfs},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    return {
        "generated_at": _now().isoformat(timespec="seconds"),
        "stats": {"requests": c.count, "blocked_403": c.blocked, "events": len(collected), "errors": errors},
        "events": collected,
    }


# =============================================================== parte MatchScorer (GitHub)

def add_matches(c: Client, ev: dict) -> None:
    ev["por_matches"] = []
    o = ev.get("oop")
    if not o or ev["status"] in ("registration_open", "registration_not_open", "finished"):
        return
    year = int(o["year"])
    days_dates: dict[int, str] = {}
    for day in range(1, int(o["totalday"]) + 1):
        try:
            res = matchscorer.parse_oop(c.get(matchscorer.url(year, o["id"], day)).text, year)
        except Exception as e:  # noqa: BLE001
            ev["warnings"].append(f"Ordem de jogo dia {day}: {e}")
            continue
        days_dates.update(res["days"])
        for m in res["matches"]:
            if matchscorer.has_nat(m, TARGET):
                ev["por_matches"].append({**m, "day": day, "date": res["days"].get(day),
                                          "local_time": res["local_time"]})
    for m in ev["por_matches"]:
        m["date"] = m["date"] or days_dates.get(m["day"])
    ev["matchscorer_id"] = f"FIP-{year}-{o['id']}"


def run_live(c: Client, fip_data: dict) -> dict:
    today = _now().date()
    events = []
    for ev in fip_data.get("events", []):
        ev = {**ev, "warnings": list(ev.get("warnings", []))}
        if ev["status"] == "registration_closed" and date.fromisoformat(ev["start"]) <= today:
            ev["status"] = "live"  # começou desde a última recolha da FIP
        if date.fromisoformat(ev["end"]) < today - timedelta(days=1):
            continue
        add_matches(c, ev)
        events.append(ev)
    age = None
    if fip_data.get("generated_at"):
        age = round((_now() - datetime.fromisoformat(fip_data["generated_at"])).total_seconds() / 3600, 1)
    return {
        "generated_at": _now().isoformat(timespec="seconds"),
        "fip_generated_at": fip_data.get("generated_at"),
        "target": TARGET,
        "stats": {
            "requests": c.count, "blocked_403": c.blocked, "events": len(events),
            "fip": fip_data.get("stats", {}), "fip_age_hours": age,
            "errors": list(fip_data.get("stats", {}).get("errors", [])),
        },
        "events": events,
    }


# =============================================================== CLI

def run(mode: str = "all", verbose: bool = False) -> dict:
    for stream in (sys.stdout, sys.stderr):  # consola/log do Windows (cp1252) vs "→", "ç"
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(message)s",
                        stream=sys.stdout)  # stdout: o PowerShell trata stderr como erro
    c = Client()
    if mode in ("fip", "all"):
        fip_data = run_fip(c, _now().date())
        FIP_OUT.parent.mkdir(parents=True, exist_ok=True)
        FIP_OUT.write_text(json.dumps(fip_data, ensure_ascii=False, indent=1), encoding="utf-8")
        log.info("FIP: %d pedidos, %d bloqueados.", c.count, c.blocked)
        if mode == "fip":
            return fip_data
    fip_data = load_json(FIP_OUT, {"events": [], "stats": {"errors": ["Ainda não chegaram dados da FIP (PC)."]}})
    c2 = Client()
    data = run_live(c2, fip_data)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("MatchScorer: %d pedidos, %d bloqueados.", c2.count, c2.blocked)
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="all", choices=["fip", "live", "all"])
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    data = run(a.mode, a.verbose)
    st = data["stats"]
    if a.mode == "fip" and (not data["events"] or st["blocked_403"] > st["requests"] / 2):
        sys.exit(1)  # o publish não envia lixo
    if a.mode == "live" and st["requests"] and st["blocked_403"] > st["requests"] / 2:
        sys.exit(1)


if __name__ == "__main__":
    main()
