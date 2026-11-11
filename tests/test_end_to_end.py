"""Corre o recolhedor completo com um cliente falso que devolve as amostras reais."""
import io
import json
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from collector import main as M
from tests.test_parsers import load_items

FX = Path(__file__).parent / "fixtures"


def _pdf_bytes():
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    items = load_items("entry_dubai_m_items.txt")
    for page in sorted({i["page"] for i in items}):
        for i in items:
            if i["page"] == page:
                c.setFont("Helvetica", 7)
                c.drawString(i["x"], i["y"], i["text"])
        c.showPage()
    c.save()
    return buf.getvalue()


class R:
    def __init__(self, text="", content=b""):
        self.text, self.content, self.status_code = text, content, 200


class FakeClient:
    def __init__(self):
        self.count = self.blocked = 0
        self.pdf = _pdf_bytes()

    def get(self, url, **kw):
        self.count += 1
        if "calendar-cupra-fip-tour" in url and "2026" in url:
            return R((FX / "calendar_cupra.html").read_text(encoding="utf-8"))
        if "calendar" in url:
            return R("<main></main>")
        if "/events/" in url:
            return R((FX / "event_dubai.html").read_text(encoding="utf-8"))
        if "matchscorerlive" in url:
            html = (FX / "ms_oop_dubai_day4.html").read_text(encoding="utf-8")
            return R(html if url.split("?")[0].endswith("/4") else html.split('<div class="row">')[0])
        if url.endswith(".pdf"):
            return R(content=self.pdf)
        raise AssertionError(url)

    def post(self, url, data, **kw):
        self.count += 1
        if data["action"] == "handle_ajax_entry":
            pdf = f"https://x/entry-{data['postID']}-{data['gender']}-v1.pdf" if data["gender"] == "M" else ""
            return R(json.dumps({"error": 404, "html": "", "pdf": pdf}))
        if data["drawType"] == "MD":
            return R(json.dumps({"error": 200, "html": (FX / "draw_dubai_md.html").read_text(encoding="utf-8"), "pdf": "https://x/md.pdf"}))
        return R(json.dumps({"error": 404, "html": "<p>No Draw Available</p>", "pdf": ""}))


def test_run(monkeypatch, tmp_path):
    monkeypatch.setattr(M, "Client", FakeClient)
    monkeypatch.setattr(M, "OUT", tmp_path / "data.json")
    monkeypatch.setattr(M, "CACHE", tmp_path / "cache.json")
    monkeypatch.setattr(M, "FIP_OUT", tmp_path / "fip.json")

    class D(M.datetime):
        @classmethod
        def now(cls, tz=None):
            return M.datetime(2026, 11, 11, 12, 0, tzinfo=tz)
    monkeypatch.setattr(M, "datetime", D)

    data = M.run("all")
    evs = {e["slug"]: e for e in data["events"]}
    assert "fip-bronze-melbourne-2026" not in evs  # já acabou
    como = evs["fip-silver-mediolanum-padel-cup-2026"]
    assert len(como["por_entries"]) == 6
    assert len(como["por_matches"]) == 1 and como["por_matches"][0]["status"] == "scheduled"
    assert como["por_matches"][0]["date"] == "2026-11-11"
    assert como["por_draws"][0]["players"][0]["name"] == "Miguel Deus"
    assert evs["premier-padel-finals-2026"]["status"] == "registration_not_open"
    assert not any(e["warnings"] for e in data["events"])
    # modo "live" sozinho (GitHub) reaproveita o fip.json e volta a ler a MatchScorer
    live = M.run("live")
    assert {e["slug"]: len(e["por_matches"]) for e in live["events"]} == {e["slug"]: len(e["por_matches"]) for e in data["events"]}
    assert live["stats"]["fip_age_hours"] is not None
    # 2.ª corrida usa a cache de PDFs (sem novo download)
    data2 = M.run("all")
    assert data2["events"][0]["por_entries"] == data["events"][0]["por_entries"]
