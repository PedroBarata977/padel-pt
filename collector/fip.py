"""Leitura do site padelfip.com: calendário, página do evento e endpoints AJAX (inscritos e quadros)."""
import json
import re
from datetime import date

from bs4 import BeautifulSoup

BASE = "https://www.padelfip.com"
AJAX = BASE + "/wp-admin/admin-ajax.php"

CALENDARS = {
    "premier": "/calendar-premier-padel/?events-year={year}",
    "cupra": "/calendar-cupra-fip-tour/?events-year={year}",
}

# Classe CSS do <article> no calendário -> (circuito, categoria legível).
# Só entram as categorias pedidas: Premier Padel + CUPRA FIP Tour (Platinum/Gold/Silver/Bronze/Finals).
CATEGORIES = {
    "fip-ppt-p1": ("Premier Padel", "P1"),
    "fip-pp-p2": ("Premier Padel", "P2"),
    "fip-ppt-major": ("Premier Padel", "Major"),
    "fip-pp-master-finals": ("Premier Padel", "Finals"),
    "fip-tour-platinum": ("CUPRA FIP Tour", "Platinum"),
    "fip-tour-gold": ("CUPRA FIP Tour", "Gold"),
    "fip-tour-silver": ("CUPRA FIP Tour", "Silver"),
    "fip-tour-bronze": ("CUPRA FIP Tour", "Bronze"),
    "fip-tour-finals": ("CUPRA FIP Tour", "Finals"),
}

STATUS = {
    "live": "live",
    "registration-closed": "registration_closed",
    "registration-open": "registration_open",
    "finished": "finished",
}

DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})\s+to\s+(\d{2})/(\d{2})/(\d{4})")


def _d(dd, mm, yyyy) -> str:
    return date(int(yyyy), int(mm), int(dd)).isoformat()


def parse_calendar(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    events = []
    for art in soup.find_all("article"):
        classes = [c for c in (art.get("class") or []) if c]
        cat_key = next((c for c in classes if c in CATEGORIES), None)
        if not cat_key:
            continue
        title_a = art.select_one(".event-title a")
        if not title_a:
            continue
        dt = art.select_one(".date-start-end")
        m = DATE_RE.search(dt.get_text(" ", strip=True) if dt else "")
        if not m:
            continue
        st_el = art.select_one(".event-status")
        st_key = next((c for c in (st_el.get("class") if st_el else []) if c in STATUS), None)
        loc = art.select_one(".event-location")
        circuit, category = CATEGORIES[cat_key]
        events.append({
            "name": title_a.get_text(strip=True),
            "url": title_a["href"],
            "slug": title_a["href"].rstrip("/").rsplit("/", 1)[-1],
            "circuit": circuit,
            "category": category,
            "location": loc.get_text(strip=True) if loc else "",
            "start": _d(*m.group(1, 2, 3)),
            "end": _d(*m.group(4, 5, 6)),
            # sem etiqueta no calendário = inscrições ainda não abriram
            "status": STATUS.get(st_key, "registration_not_open"),
        })
    return events


def parse_event_page(html: str) -> dict:
    """postID, nonce do AJAX, texto de inscrições e configuração do widget MatchScorer."""
    info = {"post_id": None, "nonce": None, "registration": None, "oop": None}
    m = re.search(r"postid-(\d+)", html)
    if m:
        info["post_id"] = m.group(1)
    m = re.search(r"var padelfip_ajax\s*=\s*(\{.*?\});", html)
    if m:
        try:
            info["nonce"] = json.loads(m.group(1)).get("nonce")
        except json.JSONDecodeError:
            pass
    m = re.search(r'class="overview__title">\s*(Registration[^<]*)<', html)
    if m:
        info["registration"] = m.group(1).strip()
    m = re.search(r"get-oop-data\.php\?([^\"']+)", html)
    if m:
        q = dict(p.split("=", 1) for p in m.group(1).replace("\\/", "/").split("&") if "=" in p)
        if q.get("id") and q.get("year"):
            info["oop"] = {
                "year": q["year"],
                "id": q["id"],
                "day": int(q.get("day", 1)),
                "totalday": int(q.get("totalday", 1)),
            }
    return info


def _ajax_headers(referer: str | None) -> dict:
    """Os mesmos cabeçalhos que a página do torneio envia quando faz este pedido (jQuery.ajax)."""
    h = {"Origin": BASE, "X-Requested-With": "XMLHttpRequest",
         "Accept": "*/*", "Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty"}
    if referer:
        h["Referer"] = referer
    return h


def ajax_entry(client, post_id: str, nonce: str, gender: str, referer: str | None = None) -> dict:
    """gender: 'M' ou 'W'. Devolve {'pdf': url|'' , 'html': ..., 'error': ...}."""
    r = client.post(AJAX, headers=_ajax_headers(referer), data={
        "action": "handle_ajax_entry", "gender": gender, "postID": post_id,
        "juniorEntryCat": "", "security": nonce,
    })
    return _json(r.text)


def ajax_draw(client, post_id: str, nonce: str, draw_type: str, referer: str | None = None) -> dict:
    """draw_type: MD, MQ, WD, WQ."""
    gender = "M" if draw_type.startswith("M") else "F"
    r = client.post(AJAX, headers=_ajax_headers(referer), data={
        "action": "handle_ajax_request", "drawType": draw_type, "gender": gender,
        "juniorCat": "", "postID": post_id, "security": nonce,
    })
    return _json(r.text)


def _json(text: str) -> dict:
    text = text.strip()
    if text in ("-1", "0", ""):
        raise RuntimeError(f"AJAX recusado (resposta '{text}') — nonce inválido?")
    return json.loads(text)
