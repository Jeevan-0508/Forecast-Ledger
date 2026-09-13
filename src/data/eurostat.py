"""
Eurostat JSON-stat fetch + parse.

Two responsibilities only:
  1. get the raw dataset from the API (or a local cache), never mutating it
  2. flatten JSON-stat into a tidy, chronologically ordered list of
     {geo, unit, period, value} records for exactly one requested series

Everything downstream (eligibility, models, backtest) consumes only the
tidy record list, never the raw JSON-stat shape.
"""
from __future__ import annotations

import json
import re
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

FREQ_LABELS = {"Q": "quarterly", "A": "annual", "M": "monthly"}


class FetchError(RuntimeError):
    pass


def _period_sort_key(period: str):
    """Chronological sort key for either '1999-Q1'/'2000Q1' style or a bare
    annual '1999'. Never relies on dict/string order."""
    m = re.match(r"^(\d{4})[-]?Q?(\d)?$", period)
    if not m:
        raise ValueError(f"unrecognised period format: {period!r}")
    year = int(m.group(1))
    sub = int(m.group(2)) if m.group(2) else 0
    return (year, sub)


@dataclass
class TidySeries:
    dataset: str
    series_id: str          # human-readable identity, e.g. "sts_trtu_q.EU27_2020.G47.VOL_SLS.I21.SCA"
    geo: str
    unit: str
    frequency: str           # "quarterly" | "annual" | "monthly"
    dataset_updated: Optional[str]   # ESTAT's own "updated" timestamp for the dataset
    fetched_at: str                  # when THIS run pulled it, UTC ISO-8601
    records: list = field(default_factory=list)   # [{"period": str, "value": float}], ascending, deduped

    def periods(self):
        return [r["period"] for r in self.records]

    def values(self):
        return [r["value"] for r in self.records]


def _cache_path(cache_dir: Path, dataset: str, query_key: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", query_key)
    return cache_dir / f"{dataset}__{safe}.json"


def fetch_raw(dataset: str, params: dict, cache_dir: Path, query_key: str,
              force_refresh: bool = False, timeout: int = 30) -> dict:
    """Return the raw JSON-stat dict for `dataset` filtered by `params`.
    Cached to `cache_dir` so a rebuild needs no network. Cache is a plain
    copy of what the API returned: this function never edits it."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(cache_dir, dataset, query_key)

    if path.exists() and not force_refresh:
        return json.loads(path.read_text(encoding="utf-8"))

    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{EUROSTAT_BASE}/{dataset}?format=JSON&lang=EN&{qs}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        raise FetchError(f"could not fetch {dataset} ({query_key}): {e}") from e

    doc = json.loads(raw)
    if doc.get("value") == {} and doc.get("size") and 0 in doc.get("size", []):
        raise FetchError(
            f"{dataset} ({query_key}): API accepted the query but matched zero "
            f"categories on at least one dimension -> empty series. Check filter codes."
        )
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return doc


def parse_jsonstat(doc: dict, dataset: str, series_id: str, geo: str, unit: str) -> TidySeries:
    """Flatten a single-series JSON-stat response into a TidySeries.
    Assumes the query already pinned every non-time dimension to one
    category (so `value` is indexed purely by the time dimension)."""
    freq_codes = list(doc["dimension"]["freq"]["category"]["label"].keys())
    if len(freq_codes) != 1:
        raise FetchError(f"expected exactly one freq category, got {freq_codes}")
    frequency = FREQ_LABELS.get(freq_codes[0], freq_codes[0])

    time_index = doc["dimension"]["time"]["category"]["index"]  # period -> position
    idx_to_period = {v: k for k, v in time_index.items()}
    if len(idx_to_period) != len(time_index):
        raise FetchError(
            f"{series_id}: two distinct time-dimension labels map to the same position; "
            f"cannot unambiguously assign observations to periods."
        )

    value_by_pos = doc.get("value", {})
    seen_periods = set()
    records = []
    for pos_str, val in value_by_pos.items():
        pos = int(pos_str)
        period = idx_to_period[pos]
        if period in seen_periods:
            raise FetchError(f"duplicate observation for period {period} in {series_id}")
        seen_periods.add(period)
        records.append({"period": period, "value": float(val)})

    records.sort(key=lambda r: _period_sort_key(r["period"]))

    return TidySeries(
        dataset=dataset,
        series_id=series_id,
        geo=geo,
        unit=unit,
        frequency=frequency,
        dataset_updated=doc.get("updated"),
        fetched_at=datetime.now(timezone.utc).isoformat(),
        records=records,
    )


def _as_int(series: TidySeries, key):
    if series.frequency == "quarterly":
        return key[0] * 4 + key[1]
    if series.frequency == "monthly":
        return key[0] * 12 + key[1]
    return key[0]  # annual


def gaps(series: TidySeries):
    """Sorted integer positions (native-period units) of every observation,
    used to compute both the largest single gap and the total missing count
    inside the observed span (never outside it -- we do not count periods
    before the first or after the last observation as "missing")."""
    keys = [_period_sort_key(p) for p in series.periods()]
    return sorted(_as_int(series, k) for k in keys)


def largest_gap(series: TidySeries) -> int:
    """Largest gap between consecutive observations, expressed in native
    periods (0 = perfectly contiguous, 1 = one missing period skipped)."""
    ints = gaps(series)
    if len(ints) < 2:
        return 0
    return max(b - a - 1 for a, b in zip(ints, ints[1:]))


def missing_count(series: TidySeries) -> int:
    """Total number of native periods missing strictly between the first and
    last observation (i.e. internal gaps only)."""
    ints = gaps(series)
    if len(ints) < 2:
        return 0
    return sum(b - a - 1 for a, b in zip(ints, ints[1:]))


def profile(series: TidySeries) -> dict:
    return {
        "dataset": series.dataset,
        "series_id": series.series_id,
        "geo": series.geo,
        "unit": series.unit,
        "frequency": series.frequency,
        "first_observation": series.periods()[0] if series.records else None,
        "last_observation": series.periods()[-1] if series.records else None,
        "observation_count": len(series.records),
        "missing_count": missing_count(series) if series.records else 0,
        "largest_gap": largest_gap(series) if series.records else None,
        "dataset_updated": series.dataset_updated,
        "fetched_at": series.fetched_at,
    }
