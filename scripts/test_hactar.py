"""Smoke-test for the Hactar (Open WebUI) endpoint using the OpenAI client."""

from __future__ import annotations

import os
import sys

from pathlib import Path

# Load .env from repo root without extra dependencies
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _, _val = _line.partition("=")
            os.environ.setdefault(_key.strip(), _val.strip().strip("'\""))

import requests  # noqa: E402

BASE_URL = os.environ.get("HACTAR_BASE_URL", "https://hactar.unige.ch")
API_KEY = os.environ.get("HACTAR_API_KEY", "")
MODEL = os.environ.get("HACTAR_MODEL", "mistral-small3.1:24b")
VERIFY_SSL = os.environ.get("HACTAR_VERIFY_SSL", "True").lower() != "false"

print(f"Base URL  : {BASE_URL}")
print(f"Model     : {MODEL}")
print(f"Verify SSL: {VERIFY_SSL}")

url = f"{BASE_URL}/api/chat/completions"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}
payload = {
    "model": MODEL,
    "messages": [
        {
            "role": "user",
            "content": "What is the capital of France? Reply in one word.",
        }
    ],
    "max_tokens": 20,
    "temperature": 0.0,
}

try:
    resp = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30,
        verify=VERIFY_SSL,  # nosec B501
    )
    print(f"Status    : {resp.status_code}")
    resp.raise_for_status()
    data = resp.json()
    reply = data["choices"][0]["message"]["content"].strip()
    assert reply, "Empty response from model"
    print(f"Reply     : {reply}")
    print("\nSUCCESS: Hactar is responding correctly.")
except requests.exceptions.HTTPError as e:
    print(f"\nFAILED (HTTP {resp.status_code}): {resp.text[:500]}")
    sys.exit(1)
except Exception as e:
    print(f"\nFAILED: {e}")
    sys.exit(1)
