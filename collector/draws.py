"""Leitura dos quadros (HTML devolvido pelo AJAX handle_ajax_request do padelfip.com)."""
from bs4 import BeautifulSoup

from .countries import nat_from_fip_flag

# data-round = número de jogos nessa coluna
ROUND_NAMES = {64: "1/64", 32: "1/32", 16: "1/16", 8: "Oitavos", 4: "Quartos", 2: "Meias", 1: "Final"}
QUALY_ROUND_NAMES = {}  # na qualificação o nº de jogos não diz a ronda final; usamos "Q1, Q2, ..."


def parse_draw(html: str, qualy: bool = False) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    cols = soup.select(".colDraw[data-round]")
    out = []
    for ci, col in enumerate(cols, start=1):
        n = int(col["data-round"])
        rname = f"Q{ci}" if qualy else ROUND_NAMES.get(n, f"Ronda {ci}")
        for m in col.select(".singleMatch"):
            teams = []
            for t in m.select(".singleMatch__team"):
                players = []
                for it in t.select(".singleMatch__team--item"):
                    img = it.find("img")
                    name = it.select_one(".singleMatch__team--itemName")
                    if name and name.find("span"):
                        name.find("span").extract()
                    players.append({
                        "name": name.get_text(strip=True) if name else "",
                        "nat": nat_from_fip_flag(img["src"]) if img else "",
                    })
                info = t.select_one(".additionalInfo")
                seed = info.find("small").get_text(strip=True).strip("()\xa0 ") if info and info.find("small") else ""
                sets = [s.get_text(strip=True) for s in t.select(".singleMatch__tableSet")]
                teams.append({
                    "id": t.get("data-single-team"),
                    "players": [p for p in players if p["name"]],
                    "seed": seed,
                    "sets": [s for s in sets if s],
                    "winner": bool(info and "✓" in info.get_text()),
                })
            if teams:
                out.append({"match_id": m.get("data-match-id"), "round": rname, "round_index": ci, "teams": teams})
    return out


def team_path(matches: list[dict], nat: str) -> list[dict]:
    """Para cada equipa com um jogador `nat`, o percurso no quadro: jogos, adversários, estado."""
    by_team: dict[str, dict] = {}
    for m in sorted(matches, key=lambda x: x["round_index"]):
        for i, t in enumerate(m["teams"]):
            if not any(p["nat"] == nat for p in t["players"]):
                continue
            key = t["id"] or "/".join(p["name"] for p in t["players"])
            entry = by_team.setdefault(key, {"players": t["players"], "seed": t["seed"], "matches": []})
            opp = m["teams"][1 - i] if len(m["teams"]) == 2 else None
            entry["matches"].append({
                "round": m["round"],
                "opponent": opp["players"] if opp else [],
                "opponent_seed": opp["seed"] if opp else "",
                "sets": t["sets"],
                "opponent_sets": opp["sets"] if opp else [],
                "won": t["winner"],
                "lost": bool(opp and opp["winner"]),
            })
    for e in by_team.values():
        last = e["matches"][-1]
        e["status"] = "eliminado" if last["lost"] else ("em prova" if not last["won"] else "venceu ronda")
    return list(by_team.values())
