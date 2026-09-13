"""
Grading: attach an outcome to a previously sealed forecast, once the target
period's real observation exists. Never edits the original contract.
"""
from __future__ import annotations

from src.data.eurostat import TidySeries
from src.ledger.contract import hash_values
from src.ledger.store import LedgerStore


def try_grade_outstanding(store: LedgerStore, series: TidySeries, config_version: str) -> list:
    """For every outstanding (sealed, ungraded) forecast whose series_id
    matches this freshly fetched series, check whether the target period
    now has an observation. If so, grade it. Idempotent: forecasts already
    graded, or whose target period still has no observation, are left
    untouched. Returns the list of newly-written GRADED events."""
    period_to_value = dict(zip(series.periods(), series.values()))
    newly_graded = []

    for fid in store.outstanding_forecasts():
        sealed = store.find_sealed(fid)
        contract = sealed["contract"]
        if contract["series_id"] != series.series_id:
            continue
        target = contract["target_period"]
        if target not in period_to_value:
            continue  # outcome does not exist yet -- correctly still AWAITING_OUTCOME

        actual = period_to_value[target]
        forecast = contract["point_forecast"]
        signed_error = actual - forecast
        pct_error = (signed_error / actual) if actual != 0 else None

        outcome = {
            "actual": actual,
            "forecast": forecast,
            "signed_error": signed_error,
            "absolute_error": abs(signed_error),
            "percentage_error": pct_error,
            "actual_data_vintage": series.dataset_updated,
            "actual_data_hash": hash_values(series.values()),
        }
        event = store.grade(fid, target, outcome, config_version)
        newly_graded.append(event)

    return newly_graded
