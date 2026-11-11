"""Leitura das Entry Lists em PDF da FIP.

Layout observado (P1 Dubai, Bronze Levante, Platinum Aguascalientes, Silver Como):
    cabeçalho:  Pos | Ranking | Player | Ranking | Player | Team Points
    linha:      "13"  "110"  "Pedro Araujo POR"   "112"  "Pedro Graça POR"   "1085"
                             "554 points"                "531 points"
    secções:    MAIN DRAW / QUALIFICATIONS / WAITING LIST (títulos centrados)
    marcas:     "38 WC" na coluna Pos, "PR" (protected ranking) junto aos pontos.

A abordagem não depende de coordenadas fixas: a fronteira entre jogador 1 e jogador 2
é a posição x do 2.º cabeçalho "Ranking" de cada página.
"""
import io
import re

from .countries import IOC

# Sobe este número sempre que o leitor mudar: obriga o PC a reler os PDFs que tem em cache.
PARSER_VERSION = 2

SECTIONS = {
    "MAIN DRAW": "main",
    "QUALIFICATIONS": "qualy",
    "QUALIFICATION": "qualy",
    "QUALIFYING": "qualy",
    "WAITING LIST": "waiting",
    "ALTERNATES": "waiting",
    "RESERVE LIST": "waiting",
}
PLAYER_RE = re.compile(r"^(.+?)\s+([A-Z]{3})$")
POS_RE = re.compile(r"^(\d{1,3})(?:\s+(WC|AWC|Q|LL|SE|JE|PR))?$")
POINTS_RE = re.compile(r"^(\d+)\s*points?", re.I)
UPDATE_RE = re.compile(r"Last Update:\s*(.+)$", re.I)


# ---------------------------------------------------------------- extração do PDF

def pdf_items(data: bytes) -> list[dict]:
    """Linhas de texto com posição: [{'page','x','y','text'}]. y cresce para cima (como no PDF)."""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LAParams, LTTextContainer, LTTextLine

    items = []
    laparams = LAParams(char_margin=1.5, line_margin=0.1, word_margin=0.1)
    for pno, page in enumerate(extract_pages(io.BytesIO(data), laparams=laparams), start=1):
        def walk(el):
            if isinstance(el, LTTextLine):
                txt = el.get_text().strip()
                if txt:
                    items.append({"page": pno, "x": round(el.x0), "y": round(el.y0), "text": txt})
            elif isinstance(el, LTTextContainer) or hasattr(el, "__iter__"):
                for c in el:
                    walk(c)
        for el in page:
            walk(el)
    return items


# ---------------------------------------------------------------- interpretação

def _split_player(text: str):
    m = PLAYER_RE.match(text)
    if m and m.group(2) in IOC:
        return m.group(1).strip(), m.group(2)
    return None


def parse_items(items: list[dict]) -> dict:
    """Converte as linhas de texto em equipas."""
    out = {"title": None, "updated": None, "gender": None, "teams": []}
    pages = sorted({i["page"] for i in items})
    section = "main"
    last_cols: list[int] = []  # colunas da última página com cabeçalho (há PDFs que não o repetem)
    for p in pages:
        pit = [i for i in items if i["page"] == p]
        for i in pit:
            t = i["text"]
            if out["updated"] is None and (m := UPDATE_RE.search(t)):
                out["updated"] = m.group(1).strip()
            if out["gender"] is None and "ENTRY LIST" in t.upper():
                out["gender"] = "W" if re.search(r"women|ladies|female", t, re.I) else "M"
        # pode haver várias linhas de cabeçalho por página (ex.: qualificação + waiting list)
        head_x = sorted({i["x"] for i in pit if i["text"] == "Ranking"})
        head_cols = []
        for x in head_x:  # agrupar x quase iguais
            if not head_cols or x - head_cols[-1] > 20:
                head_cols.append(x)
        if head_cols:
            last_cols = head_cols
        else:
            head_cols = last_cols
        heads = [{"x": x} for x in head_cols]
        pos_heads = [i for i in pit if i["text"] == "Pos"]
        split_x = head_cols[1] if len(head_cols) >= 2 else None
        pos_max_x = (min(h["x"] for h in heads) - 2) if heads else 140

        # Marcadores verticais: títulos de secção e linhas (coluna Pos), de cima para baixo
        markers = []
        for i in pit:
            up = i["text"].upper()
            if up in SECTIONS:
                markers.append(("section", i["y"], SECTIONS[up]))
            elif i["x"] <= pos_max_x and POS_RE.match(i["text"]) and not any(abs(i["y"] - h["y"]) < 3 for h in pos_heads):
                markers.append(("row", i["y"], i))
        markers.sort(key=lambda m: -m[1])

        rows = [m for m in markers if m[0] == "row"]
        players = [(i, _split_player(i["text"])) for i in pit]
        players = [(i, sp) for i, sp in players if sp]
        points = [i for i in pit if POINTS_RE.match(i["text"])]
        # "PR" pode vir sozinho ou colado aos pontos ("1328 pointsPR"), conforme o extrator
        prs = [i for i in pit if re.search(r"(\b|points)PR\b", i["text"])]

        def row_of(item, tol=7):
            best = None
            for _, y, r in rows:
                d = item["y"] - y  # nomes ficam ~4 acima da linha base de "Pos", pontos ~4 abaixo
                if abs(d) <= tol and (best is None or abs(d) < abs(best[0])):
                    best = (d, r)
            return best[1] if best else None

        team_by_row: dict[int, dict] = {}
        for kind, y, val in markers:
            if kind == "section":
                section = val
                continue
            r = val
            pm = POS_RE.match(r["text"])
            team_by_row[id(r)] = {
                "section": section,
                "pos": int(pm.group(1)),
                "mark": pm.group(2) or "",
                "players": [None, None],
                "points": [None, None],
                "pr": False,
                "team_points": None,
                "_y": y,
            }
        for i, (name, nat) in players:
            r = row_of(i)
            if r is None:
                continue
            col = 1 if (split_x is not None and i["x"] >= split_x) else 0
            slots = team_by_row[id(r)]["players"]
            if slots[col] is not None:  # rede de segurança: nunca apagar um jogador já lido
                if slots[1 - col] is not None:
                    continue
                col = 1 - col
            slots[col] = {"name": name, "nat": nat}
        for i in points:
            r = row_of(i)
            if r is None:
                continue
            col = 1 if (split_x is not None and i["x"] >= split_x) else 0
            team_by_row[id(r)]["points"][col] = int(POINTS_RE.match(i["text"]).group(1))
        for i in prs:
            r = row_of(i)
            if r is not None:
                team_by_row[id(r)]["pr"] = True
        for t in sorted(team_by_row.values(), key=lambda t: -t["_y"]):
            t.pop("_y")
            for k, pl in enumerate(t["players"]):
                if pl:
                    pl["points"] = t["points"][k]
            t["players"] = [pl for pl in t["players"] if pl]
            t.pop("points")
            if t["players"]:
                out["teams"].append(t)
    return out


def parse_pdf(data: bytes) -> dict:
    return parse_items(pdf_items(data))


def teams_with(parsed: dict, nat: str) -> list[dict]:
    return [t for t in parsed["teams"] if any(p["nat"] == nat for p in t["players"])]
