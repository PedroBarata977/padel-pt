"""Leitura do widget MatchScorer Live (ordem de jogo por dia, com resultados e live score)."""
import re
from datetime import date

from bs4 import BeautifulSoup

from .countries import nat_from_ms_flag

WIDGET = "https://widget.matchscorerlive.com/screen/oopbyday/FIP-{year}-{id}/{day}?t=tol"

MONTHS = {m: i for i, m in enumerate(
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), start=1)}


def url(year, tid, day) -> str:
    return WIDGET.format(year=year, id=tid, day=day)


def parse_days(soup, year: int) -> dict[int, str]:
    """Separadores 'NOV 11 WED' -> {4: '2026-11-11'}."""
    days = {}
    for a in soup.find_all("a", href=True):
        m = re.search(r"/screen/oopbyday/FIP-\d+-\d+/(\d+)", a["href"])
        t = re.match(r"\s*([A-Z]{3})\s+(\d{1,2})", a.get_text(" ", strip=True).upper())
        if m and t and t.group(1) in MONTHS:
            try:
                days[int(m.group(1))] = date(year, MONTHS[t.group(1)], int(t.group(2))).isoformat()
            except ValueError:
                pass
    return days


def _team(tr) -> dict:
    players = []
    for row in tr.select(".player-names .d-flex.align-items-center"):
        img = row.find("img", class_="flags")
        spans = [s.get_text(strip=True) for s in row.select(".line-thin > span")]
        tag = row.select_one(".line-thin small")
        players.append({
            "name": " ".join(spans).strip(),
            "nat": nat_from_ms_flag(img["src"]) if img else "",
            "tag": tag.get_text(strip=True).strip("()") if tag else "",
        })
    sets = []
    for td in tr.find_all("td", class_="set"):
        v = td.get_text(strip=True)
        sets.append(None if v in ("", "-") else v)
    pts = tr.find("td", class_="points")
    return {
        "players": players,
        # cabeça de série / Q / WC aparecem no 2.º jogador
        "seed": next((p["tag"] for p in players if p["tag"]), ""),
        "sets": sets,
        "points": pts.get_text(strip=True) if pts else None,
        "serving": bool(tr.find("img", class_="ballg")),
    }


def _set_games(v):
    """'63' (tie-break 6 com 3 no TB) -> 6 ; '7' -> 7."""
    if v is None:
        return None
    v = re.sub(r"\D", "", v)
    if not v:
        return None
    if len(v) >= 2 and v[0] in "67":
        return int(v[0])  # jogos + pontos do tie-break colados
    return int(v)  # inclui super tie-break (10, 11, ...)


def _winner(t1, t2):
    w1 = w2 = 0
    for a, b in zip(t1["sets"], t2["sets"]):
        a, b = _set_games(a), _set_games(b)
        if a is None or b is None:
            continue
        if a > b:
            w1 += 1
        elif b > a:
            w2 += 1
    if w1 == w2:
        return None
    return 0 if w1 > w2 else 1


def parse_oop(html: str, year: int) -> dict:
    soup = BeautifulSoup(html, "lxml")
    days = parse_days(soup, year)
    lt = soup.select_one(".local-time")
    matches = []
    for block in soup.select(".schedule-header"):
        court_el = block.select_one(".oop-court")
        court = court_el.get_text(strip=True) if court_el else ""
        # as tabelas de jogos deste campo são irmãs seguintes do cabeçalho
        for table in block.find_next_siblings("table"):
            header = table.find("tr")
            team_rows = [tr for tr in table.find_all("tr") if tr.find("td", class_="team")]
            if len(team_rows) != 2:
                continue
            slot = header.select_one(".court-name")
            rnd = header.select_one(".round-name")
            gender = rnd.find("b").get_text(strip=True) if rnd and rnd.find("b") else ""
            rname = rnd.find("div").get_text(strip=True) if rnd and rnd.find("div") else ""
            t1, t2 = _team(team_rows[0]), _team(team_rows[1])
            summary = table.select_one(".live-status-summary")
            sum_txt = [s.get_text(strip=True) for s in summary.find_all("span")] if summary else []
            duration = next((s for s in sum_txt if re.fullmatch(r"\d{1,2}:\d{2}", s)), None)
            stats = table.select_one("a[data-id]")
            if t1["points"] is not None or t2["points"] is not None:
                status = "live"
            elif any(s.lower() == "completed" for s in sum_txt) or table.select("td.set-completed"):
                status = "completed"
            else:
                status = "scheduled"
            # "Ganhador/es do jogo X" ainda por definir
            tbd = not t1["players"] or not t2["players"]
            matches.append({
                "match_id": stats["data-id"] if stats else None,
                "court": court,
                "slot": slot.get_text(strip=True) if slot else "",
                "gender": gender,
                "round": rname,
                "teams": [t1, t2],
                "status": status,
                "duration": duration,
                "winner": _winner(t1, t2) if status == "completed" else None,
                "tbd": tbd,
                "tbd_text": [r.get_text(" ", strip=True) for r in team_rows] if tbd else None,
            })
    return {"days": days, "local_time": lt.get_text(strip=True) if lt else None, "matches": matches}


def has_nat(match: dict, nat: str) -> bool:
    if any(p["nat"] == nat for t in match["teams"] for p in t["players"]):
        return True
    # equipas ainda por definir: "A. Silva/B. Costa OR ..." não traz bandeira — procurar texto não é fiável
    return False
