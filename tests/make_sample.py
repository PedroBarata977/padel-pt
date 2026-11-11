"""Gera docs/sample-data.json (dados de EXEMPLO para ver o dashboard sem rede).

Base: amostras reais de 11/11/2026. Um jogo foi posto "ao vivo" artificialmente para mostrar o live score.
Correr: python -m tests.make_sample
"""
import copy
import json
from pathlib import Path

import pytest  # noqa: F401  (monkeypatch manual abaixo)

from collector import main as M
from tests.test_end_to_end import FakeClient

ROOT = Path(__file__).resolve().parent.parent


def build():
    M.Client = FakeClient
    tmp = ROOT / "data" / "_sample_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    M.OUT, M.CACHE = tmp / "data.json", tmp / "cache.json"
    real_dt = M.datetime

    class D(real_dt):
        @classmethod
        def now(cls, tz=None):
            return real_dt(2026, 11, 11, 15, 40, tzinfo=tz)
    M.datetime = D
    data = M.run()
    M.datetime = real_dt

    evs = {e["slug"]: e for e in data["events"]}
    # 1) Dubai P1 (live): partir do Silver de Como (mesmas amostras) e dar-lhe identidade de P1
    dubai = copy.deepcopy(evs["fip-silver-mediolanum-padel-cup-2026"])
    dubai.update(name="EMAAR DUBAI PREMIER PADEL P1", slug="emaar-dubai-premier-padel-p1-2026",
                 url="https://www.padelfip.com/events/emaar-dubai-premier-padel-p1-2026/",
                 circuit="Premier Padel", category="P1", location="Dubai - United Arab Emirates",
                 start="2026-11-08", end="2026-11-15")
    m = dubai["por_matches"][0]
    m["day"], m["date"] = 4, "2026-11-11"
    live = copy.deepcopy(m)
    live.update(status="live", duration="00:52", court="COURT 2", slot="Followed by", gender="Men",
                round="Round of 32", match_id="MD030")
    live["teams"] = [
        {"players": [{"name": "M. Deus", "nat": "POR", "tag": ""}, {"name": "N. Deus", "nat": "POR", "tag": ""}],
         "seed": "", "sets": ["6", "3", None], "points": "40", "serving": True},
        {"players": [{"name": "A. Coello", "nat": "ESP", "tag": ""}, {"name": "A. Tapia", "nat": "ARG", "tag": "1"}],
         "seed": "1", "sets": ["4", "5", None], "points": "15", "serving": False},
    ]
    dubai["por_matches"].insert(0, live)
    # 2) Como: sem portugueses em jogo; manter só a lista de inscritos de exemplo vazia
    como = evs["fip-silver-mediolanum-padel-cup-2026"]
    como.update(por_matches=[], por_draws=[], por_entries=[])
    # 3) Levante (inscrições fechadas): manter inscritos, tirar jogos/quadros
    lev = evs["fip-bronze-levante-2026"]
    lev.update(por_matches=[], por_draws=[], por_entries=[e for e in lev["por_entries"] if e["section"] == "main"],
               entry_lists={"M": {"pdf": "https://www.padelfip.com/wp-content/uploads/2025/12/entry-list-Fip-Bronze-Levante-M-v7.pdf",
                                  "updated": "08/11/2026 h 11:25 am", "n_teams": 40}})
    data["events"] = [dubai, como, lev, evs["fip-silver-roeselare-2026"], evs["premier-padel-finals-2026"]]
    evs["fip-silver-roeselare-2026"].update(por_entries=[], por_matches=[], por_draws=[], entry_lists={"M": {"pdf": None}, "W": {"pdf": None}})
    data["sample"] = True
    (ROOT / "docs" / "sample-data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ok", [e["name"] for e in data["events"]])


if __name__ == "__main__":
    build()
