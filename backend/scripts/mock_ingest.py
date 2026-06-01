"""Drop example emails into the API (mock listener for dev).

Usage (from backend/, API must be running):
    python scripts/mock_ingest.py
"""

import json
import sys
from pathlib import Path

import httpx

API = "http://127.0.0.1:8000"
EXAMPLES = Path(__file__).resolve().parent.parent / "data" / "phase_1_email_triage_examples.json"


def main() -> None:
    examples = json.loads(EXAMPLES.read_text(encoding="utf-8"))["examples"]
    for ex in examples:
        payload = {"email": ex["input"], "source": "mock_script"}
        r = httpx.post(f"{API}/messages", json=payload, timeout=30.0)
        r.raise_for_status()
        message_id = r.json()["id"]
        print(f"Ingested {ex['id']} -> {message_id}")
    print("Done. Analyze via POST /messages/{id}/analyze or the API docs.")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        sys.exit(1)
