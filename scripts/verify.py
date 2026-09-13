#!/usr/bin/env python3
"""
Independent ledger integrity check. Exit code 0 for VERIFIED or WARNING,
1 for INVALID (so CI can fail loudly on real corruption).

Usage:
    python scripts/verify.py
"""
import _pathfix  # noqa: F401
import json
import sys
from pathlib import Path

from src.ledger.store import LedgerStore
from src.ledger.verify import verify

ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = ROOT / "data" / "ledger" / "ledger.jsonl"


def main():
    store = LedgerStore(LEDGER_PATH)
    events = store.read_all()
    report = verify(events)
    print(json.dumps(report, indent=2))
    sys.exit(1 if report["status"] == "INVALID" else 0)


if __name__ == "__main__":
    main()
