"""Quick smoke-test for the Hactar (Open WebUI) endpoint."""

from __future__ import annotations

import os
import sys

from pathlib import Path

import requests

# Load .env from repo root
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _, _val = _line.partition("=")
            os.environ.setdefault(_key.strip(), _val.strip().strip("'\""))

BASE_URL = os.environ.get("HACTAR_BASE_URL", "https://hactar.unige.ch")
API_KEY = os.environ.get("HACTAR_API_KEY", "")
MODEL = os.environ.get("HACTAR_MODEL", "mistral-small3.1:24b")

url = f"{BASE_URL}/api/chat/completions"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}
payload = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "Reply with just: OK"}],
    "max_tokens": 10,
}

print(f"POST {url}")
print(f"Model: {MODEL}")

try:
    resp = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30,
        verify=False,  # nosec B501
    )
    print(f"Status: {resp.status_code}")
    if resp.ok:
        data = resp.json()
        reply = data["choices"][0]["message"]["content"].strip()
        print(f"Reply: {reply}")
    else:
        print(f"Error: {resp.text[:500]}")
        sys.exit(1)
except requests.exceptions.RequestException as e:
    print(f"Connection error: {e}")
    sys.exit(1)
