#!/usr/bin/env python3
"""
Pull both series from Eurostat into data/raw/ (cached, so a rebuild needs no
network unless --force-refresh is given), flatten into tidy JSON under
data/processed/, and write data/processed/data_profile.json -- the Phase 0
inspection artifact.

Usage:
    python scripts/fetch.py [--force-refresh]
"""
import _pathfix  # noqa: F401
import argparse
import json
import sys
from pathlib import Path

from src import config
from src.data.eurostat import fetch_raw, parse_jsonstat, profile, FetchError

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-refresh", action="store_true")
    args = ap.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    profiles = []
    documents = {}
    failures = []

    for key, spec in config.SERIES.items():
        print(f"fetching {key} ({spec['dataset']}, geo={spec['geo']})...")
        try:
            raw = fetch_raw(spec["dataset"], spec["params"], RAW_DIR, key,
                             force_refresh=args.force_refresh)
        except FetchError as e:
            print(f"  FAILED: {e}")
            failures.append(f"{key}: {e}")
            continue

        series = parse_jsonstat(raw, spec["dataset"], spec["series_id"], spec["geo"], spec["unit"])
        out_path = PROCESSED_DIR / f"{key}.json"
        fetched_at = series.fetched_at
        # A scheduled refresh must not create a commit merely because the
        # retrieval clock moved. Preserve the prior retrieval timestamp when
        # Eurostat returned the same observations and dataset vintage. A real
        # data change still gets a new timestamp and flows through the ledger.
        if out_path.exists():
            try:
                previous = json.loads(out_path.read_text(encoding="utf-8"))
                same_series = all([
                    previous.get("dataset") == series.dataset,
                    previous.get("series_id") == series.series_id,
                    previous.get("geo") == series.geo,
                    previous.get("unit") == series.unit,
                    previous.get("frequency") == series.frequency,
                    previous.get("dataset_updated") == series.dataset_updated,
                    previous.get("records") == series.records,
                ])
                if same_series and previous.get("fetched_at"):
                    fetched_at = previous["fetched_at"]
            except (OSError, json.JSONDecodeError):
                # A malformed prior artifact is allowed to be repaired by the
                # current valid response; do not hide the repair.
                pass

        documents[key] = {
            "dataset": series.dataset,
            "series_id": series.series_id,
            "geo": series.geo,
            "unit": series.unit,
            "frequency": series.frequency,
            "role": spec["role"],
            "description": spec["description"],
            "dataset_updated": series.dataset_updated,
            "fetched_at": fetched_at,
            "records": series.records,
        }

        p = profile(series)
        p["fetched_at"] = fetched_at
        p["role"] = spec["role"]
        p["description"] = spec["description"]
        profiles.append(p)
        print(f"  {p['observation_count']} observations, "
              f"{p['first_observation']} .. {p['last_observation']}, "
              f"missing_count={p['missing_count']}, largest_gap={p['largest_gap']}")

    if failures:
        print("\nFetch failed; preserving the last valid processed state:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    for key, document in documents.items():
        (PROCESSED_DIR / f"{key}.json").write_text(
            json.dumps(document, indent=2), encoding="utf-8"
        )

    (PROCESSED_DIR / "data_profile.json").write_text(
        json.dumps({"generated_by": "scripts/fetch.py", "series": profiles}, indent=2),
        encoding="utf-8",
    )
    print(f"\nwrote {PROCESSED_DIR / 'data_profile.json'}")


if __name__ == "__main__":
    raise SystemExit(main())
