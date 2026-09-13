#!/usr/bin/env python3
"""
Assembles one JSON file the static site reads: site/data.json. Every number
in it is copied from an already-generated artifact (data_profile.json, the
per-series backtest JSON, and the ledger) -- nothing here is hand-typed.

Usage:
    python scripts/build_site_data.py
"""
import _pathfix  # noqa: F401
import json
from pathlib import Path

from src.ledger.store import LedgerStore
from src.ledger.verify import verify

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
LEDGER_PATH = ROOT / "data" / "ledger" / "ledger.jsonl"
SITE_DIR = ROOT / "site"


def main():
    SITE_DIR.mkdir(exist_ok=True)
    store = LedgerStore(LEDGER_PATH)
    events = store.read_all()
    integrity = verify(events)

    profile = json.loads((PROCESSED_DIR / "data_profile.json").read_text(encoding="utf-8"))

    series_data = {}
    for f in PROCESSED_DIR.glob("*.json"):
        if f.name == "data_profile.json" or f.name.endswith("_backtest.json"):
            continue
        doc = json.loads(f.read_text(encoding="utf-8"))
        series_data[f.stem] = doc

    backtests = {}
    for f in PROCESSED_DIR.glob("*_backtest.json"):
        key = f.stem.replace("_backtest", "")
        backtests[key] = json.loads(f.read_text(encoding="utf-8"))

    sealed = [e for e in events if e["event"] == "SEALED"]
    graded = {e["forecast_id"]: e for e in events if e["event"] == "GRADED"}
    refused = [e for e in events if e["event"] == "REFUSED"]

    ledger_view = []
    for e in sealed:
        c = e["contract"]
        entry = {
            "forecast_id": c["forecast_id"],
            "series_id": c["series_id"],
            "forecast_origin": c["forecast_origin"],
            "target_period": c["target_period"],
            "model": c["model"],
            "backtest_mase": c["backtest_mase"],
            "point_forecast": c["point_forecast"],
            "hash": e["hash"],
            "sealed_at": e["sealed_at"],
            "status": "GRADED" if c["forecast_id"] in graded else "AWAITING_OUTCOME",
        }
        if c["forecast_id"] in graded:
            g = graded[c["forecast_id"]]
            entry["actual"] = g["actual"]
            entry["signed_error"] = g["signed_error"]
            entry["absolute_error"] = g["absolute_error"]
        ledger_view.append(entry)

    refusal_view = [{
        "dataset": e["dataset"],
        "series_id": e["series_id"],
        "observations": e["observations"],
        "required_observations": e["eligibility"]["required_observations"],
        "reason_code": e["reason_code"],
        "reason": e["reason"],
        "timestamp": e["timestamp"],
        "checked_rules": e["eligibility"]["checked_rules"],
    } for e in refused]

    out = {
        "generated_by": "scripts/build_site_data.py",
        "data_profile": profile,
        "series": series_data,
        "backtests": backtests,
        "ledger": ledger_view,
        "refusals": refusal_view,
        "integrity": integrity,
        "counts": {
            "sealed": len(sealed),
            "graded": len(graded),
            "refused": len(refused),
        },
    }
    (SITE_DIR / "data.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {SITE_DIR / 'data.json'} "
          f"(sealed={len(sealed)}, graded={len(graded)}, refused={len(refused)}, "
          f"integrity={integrity['status']})")


if __name__ == "__main__":
    main()
