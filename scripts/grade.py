#!/usr/bin/env python3
"""
Grade any outstanding sealed forecast whose target period now has a real
observation. Never edits a sealed contract -- only appends GRADED events.

Usage:
    python scripts/grade.py
"""
import _pathfix  # noqa: F401
import json
from pathlib import Path

from src import config
from src.data.eurostat import TidySeries
from src.grading.grade import try_grade_outstanding
from src.ledger.store import LedgerStore

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
LEDGER_PATH = ROOT / "data" / "ledger" / "ledger.jsonl"


def load_series(key: str) -> TidySeries:
    doc = json.loads((PROCESSED_DIR / f"{key}.json").read_text(encoding="utf-8"))
    return TidySeries(
        dataset=doc["dataset"], series_id=doc["series_id"], geo=doc["geo"], unit=doc["unit"],
        frequency=doc["frequency"], dataset_updated=doc["dataset_updated"], fetched_at=doc["fetched_at"],
        records=doc["records"],
    )


def main():
    store = LedgerStore(LEDGER_PATH)
    outstanding = store.outstanding_forecasts()
    if not outstanding:
        print("no outstanding sealed forecasts.")
        return

    print(f"{len(outstanding)} outstanding forecast(s): {outstanding}")
    graded_total = []
    for key in config.SERIES:
        series = load_series(key)
        newly = try_grade_outstanding(store, series, config.CONFIG_VERSION)
        for event in newly:
            print(f"GRADED {event['forecast_id']}: actual={event['actual']} "
                  f"forecast={event['forecast']} signed_error={event['signed_error']:+.3f}")
        graded_total.extend(newly)

    if not graded_total:
        print("no target periods have a published observation yet -- still AWAITING_OUTCOME.")


if __name__ == "__main__":
    main()
