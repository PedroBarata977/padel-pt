"""Cliente HTTP educado: um só Session, user-agent de browser, retries e pausa entre pedidos."""
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
PAUSE = 0.6  # segundos entre pedidos — não queremos martelar o site


class Client:
    def __init__(self, pause: float = PAUSE):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,pt-PT;q=0.8",
        })
        retry = Retry(total=3, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=("GET", "POST"))
        self.s.mount("https://", HTTPAdapter(max_retries=retry))
        self.pause = pause
        self.count = 0
        self.blocked = 0  # respostas 403 (Cloudflare) — é o indicador do "kill switch"

    def _wait(self):
        if self.count:
            time.sleep(self.pause)
        self.count += 1

    def get(self, url: str, **kw) -> requests.Response:
        self._wait()
        r = self.s.get(url, timeout=30, **kw)
        self._diag(r)
        r.raise_for_status()
        return r

    def _diag(self, r):
        if r.status_code == 403:
            self.blocked += 1
            if self.blocked <= 2:  # diagnóstico: que tipo de bloqueio?
                h = r.headers
                print(f"  403 {r.url[:80]} server={h.get('server')} cf-mitigated={h.get('cf-mitigated')} "
                      f"cf-ray={h.get('cf-ray')} body={r.text[:160]!r}")

    def post(self, url: str, data: dict, **kw) -> requests.Response:
        self._wait()
        r = self.s.post(url, data=data, timeout=30, **kw)
        self._diag(r)
        r.raise_for_status()
        return r
