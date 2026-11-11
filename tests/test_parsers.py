"""Testes dos parsers contra amostras reais (11/11/2026). Correr: python -m pytest -q"""
import io
from pathlib import Path

import pytest

from collector import draws, entrylist, fip, matchscorer

FX = Path(__file__).parent / "fixtures"


def load_items(name):
    items, page = [], 0
    for line in (FX / name).read_text(encoding="utf-8").splitlines():
        if line.startswith("#page"):
            page += 1
            continue
        x, y, text = line.split("|", 2)
        items.append({"page": page, "x": int(x), "y": int(y), "text": text})
    return items


# ------------------------------------------------------------------ calendário / evento

def test_calendar():
    ev = fip.parse_calendar((FX / "calendar_cupra.html").read_text(encoding="utf-8"))
    by = {e["slug"]: e for e in ev}
    assert "x" not in by  # Promises fica de fora
    assert by["fip-silver-mediolanum-padel-cup-2026"]["status"] == "live"
    assert by["fip-silver-mediolanum-padel-cup-2026"]["start"] == "2026-11-10"
    assert by["fip-bronze-levante-2026"]["status"] == "registration_closed"
    assert by["fip-silver-roeselare-2026"]["status"] == "registration_open"
    assert by["fip-bronze-melbourne-2026"]["status"] == "finished"
    assert by["premier-padel-finals-2026"]["status"] == "registration_not_open"
    assert by["premier-padel-finals-2026"]["circuit"] == "Premier Padel"


def test_event_page():
    info = fip.parse_event_page((FX / "event_dubai.html").read_text(encoding="utf-8"))
    assert info["post_id"] == "290236"
    assert info["nonce"] == "8c69a37193"
    assert info["registration"] == "Registration Closed"
    assert info["oop"] == {"year": "2026", "id": "4501", "day": 4, "totalday": 8}


# ------------------------------------------------------------------ MatchScorer

def test_oop():
    res = matchscorer.parse_oop((FX / "ms_oop_dubai_day4.html").read_text(encoding="utf-8"), 2026)
    assert res["days"][4] == "2026-11-11"
    m = res["matches"]
    assert len(m) == 4
    done, por, live, tb = m
    assert done["status"] == "completed" and done["winner"] == 1 and done["duration"] == "01:02"
    assert por["status"] == "scheduled" and por["slot"] == "Followed by" and por["court"] == "CENTER COURT"
    assert matchscorer.has_nat(por, "POR") and not matchscorer.has_nat(done, "POR")
    assert por["teams"][1]["players"][0] == {"name": "S. Araujo", "nat": "POR", "tag": ""}
    assert por["teams"][1]["seed"] == "5" and por["teams"][0]["seed"] == "Q"
    assert por["gender"] == "Women" and por["round"] == "Round of 32"
    assert live["status"] == "live"
    assert live["teams"][0]["points"] == "0" and live["teams"][1]["points"] == "30"
    assert live["teams"][0]["serving"] and not live["teams"][1]["serving"]
    assert live["teams"][0]["sets"] == ["6", "4", "2"]
    assert tb["winner"] == 0  # 7-6(3) 7-6(5)


# ------------------------------------------------------------------ quadros

def test_draw_path():
    ms = draws.parse_draw((FX / "draw_dubai_md.html").read_text(encoding="utf-8"))
    assert [x["round"] for x in ms] == ["1/32", "1/16"]
    path = draws.team_path(ms, "POR")
    assert len(path) == 1
    p = path[0]
    assert [pl["name"] for pl in p["players"]] == ["Miguel Deus", "Nuno Deus"]
    assert p["matches"][0]["won"] and p["matches"][0]["sets"] == ["6", "7"]
    assert p["matches"][1]["opponent"][0]["name"] == "Arturo Coello"
    assert p["matches"][1]["opponent_seed"] == "1"
    assert p["status"] == "em prova"


# ------------------------------------------------------------------ entry lists

def _check_dubai(parsed):
    assert parsed["updated"].startswith("07/11/2026")
    assert parsed["gender"] == "M"
    por = entrylist.teams_with(parsed, "POR")
    names = [[p["name"] for p in t["players"]] for t in por]
    assert names == [
        ["Miguel Deus", "Nuno Deus"],
        ["Pedro Araujo", "Pedro Graça"],
        ["Gustavo Nunes", "Anton Sans"],
        ["Diogo Jesus", "Antonio Luque"],
        ["João Maria Caiano", "Alejandro Calvo Perez"],
        ["Pedro Perry", "Afonso Fazendeiro"],
    ]
    assert [t["section"] for t in por] == ["main", "qualy", "qualy", "qualy", "qualy", "waiting"]
    deus = por[0]
    assert deus["pos"] == 33 and deus["pr"] and deus["players"][0]["points"] == 1328
    wc = [t for t in parsed["teams"] if t["mark"] == "WC"]
    assert [t["pos"] for t in wc] == [38, 32]
    assert parsed["teams"][0]["players"][1] == {"name": "Agustin Tapia", "nat": "ARG", "points": 21906}


def test_entry_items():
    _check_dubai(entrylist.parse_items(load_items("entry_dubai_m_items.txt")))


def test_entry_real_pdf_roundtrip():
    """Gera um PDF com o mesmo layout (coordenadas reais) e lê-o com o pdfminer."""
    reportlab = pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    font = "Helvetica"
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",):
        if Path(path).exists():
            pdfmetrics.registerFont(TTFont("DejaVu", path))
            font = "DejaVu"
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    items = load_items("entry_dubai_m_items.txt")
    for page in sorted({i["page"] for i in items}):
        for i in items:
            if i["page"] == page:
                c.setFont(font, 7)
                c.drawString(i["x"], i["y"], i["text"])
        c.showPage()
    c.save()
    _check_dubai(entrylist.parse_pdf(buf.getvalue()))
