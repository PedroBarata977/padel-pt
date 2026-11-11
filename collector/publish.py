"""Envia docs/fip.json para o GitHub pela API (sem precisar de git instalado no Windows).

Token: ficheiro github_token.txt na raiz do projeto (fica só no teu PC, está no .gitignore),
ou variável de ambiente GITHUB_TOKEN. Usa um "fine-grained token" com acesso só ao
repositório padel-pt e permissão "Contents: Read and write".
"""
import base64
import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
REPO = os.environ.get("PADEL_REPO", "PedroBarata977/padel-pt")
FILES = ["docs/fip.json"]


def token() -> str:
    t = os.environ.get("GITHUB_TOKEN")
    f = ROOT / "github_token.txt"
    if not t and f.exists():
        t = f.read_text(encoding="utf-8").strip()
    if not t:
        sys.exit("Falta o token do GitHub (github_token.txt).")
    return t


def put(path: str, tok: str) -> str:
    api = f"https://api.github.com/repos/{REPO}/contents/{path}"
    h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    content = (ROOT / path).read_bytes()
    r = requests.get(api, headers=h, params={"ref": "main"}, timeout=30)
    sha = r.json().get("sha") if r.status_code == 200 else None
    if sha:
        cur = requests.get(api, headers={**h, "Accept": "application/vnd.github.raw+json"},
                           params={"ref": "main"}, timeout=30)
        if cur.status_code == 200 and cur.content == content:
            return "igual, não enviado"
    body = {"message": f"fip: {json.loads(content).get('generated_at', '')}",
            "content": base64.b64encode(content).decode(), "branch": "main"}
    if sha:
        body["sha"] = sha
    r = requests.put(api, headers=h, json=body, timeout=60)
    if r.status_code not in (200, 201):
        sys.exit(f"GitHub recusou {path}: HTTP {r.status_code} {r.text[:300]}")
    return "enviado"


def main():
    tok = token()
    for p in FILES:
        print(p, "→", put(p, tok))


if __name__ == "__main__":
    main()
