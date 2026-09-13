"""
Deterministic eligibility engine.

Every threshold it checks lives in src.config, each with a written-down
methodological reason. This module only applies them and reports which one
failed first. It never sees which dataset it is being asked about and makes
no dataset-specific exception.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

from src import config
from src.data.eurostat import TidySeries, largest_gap, missing_count


@dataclass
class EligibilityResult:
    status: str                 # "ELIGIBLE" | "REFUSED"
    dataset: str
    series_id: str
    reason_code: str
    message: str
    observations: int
    required_observations: int
    frequency: str
    season_length: int
    largest_gap: int
    max_allowed_gap: int
    config_version: str
    checked_rules: list          # every rule evaluated, in order, with pass/fail

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate(series: TidySeries) -> EligibilityResult:
    m = config.SEASON_LENGTH_BY_FREQUENCY.get(series.frequency)
    checks = []

    def check(name, passed, detail):
        checks.append({"rule": name, "passed": passed, "detail": detail})
        return passed

    # Rule 1: frequency must be one this protocol knows a season length for.
    ok = check(
        "KNOWN_FREQUENCY",
        m is not None,
        f"frequency={series.frequency!r}",
    )
    if not ok:
        return _refused(series, "UNSUPPORTED_FREQUENCY",
                         f"No season length is defined for frequency {series.frequency!r}.",
                         checks, m or 0)

    n = len(series.records)
    required = config.required_observations(m)
    ok = check(
        "MIN_OBSERVATIONS",
        n >= required,
        f"observations={n}, required={required} "
        f"(min_train={config.min_train(m)} + "
        f"{config.MIN_INDEPENDENT_TEST_WINDOWS} independent windows x horizon {config.MAX_HORIZON})",
    )
    if not ok:
        return EligibilityResult(
            status="REFUSED",
            dataset=series.dataset,
            series_id=series.series_id,
            reason_code="INSUFFICIENT_HISTORY",
            message=(
                f"{n} usable observations cannot support the configured evaluation "
                f"protocol (needs {required}: {config.min_train(m)} to train plus "
                f"{config.MIN_INDEPENDENT_TEST_WINDOWS} independent {config.MAX_HORIZON}-step "
                f"test windows). Producing a forecast would be easier than defending one."
            ),
            observations=n,
            required_observations=required,
            frequency=series.frequency,
            season_length=m,
            largest_gap=largest_gap(series),
            max_allowed_gap=config.MAX_ALLOWED_INTERNAL_GAP,
            config_version=config.CONFIG_VERSION,
            checked_rules=checks,
        )

    gap = largest_gap(series)
    ok = check(
        "CONTIGUOUS_HISTORY",
        gap <= config.MAX_ALLOWED_INTERNAL_GAP,
        f"largest_gap={gap} periods, max_allowed={config.MAX_ALLOWED_INTERNAL_GAP}",
    )
    if not ok:
        return _refused(series, "NON_CONTIGUOUS_HISTORY",
                         f"Largest internal gap is {gap} periods, exceeding the "
                         f"{config.MAX_ALLOWED_INTERNAL_GAP}-period tolerance for an "
                         f"honest training window.", checks, m,
                         observations=n, required=required, gap=gap)

    values = series.values()
    variance_ok = len(set(values)) > 1
    ok = check("NON_DEGENERATE_VARIANCE", variance_ok, f"distinct_values={len(set(values))}")
    if not ok:
        return _refused(series, "DEGENERATE_SERIES",
                         "Series is constant; there is nothing to forecast.",
                         checks, m, observations=n, required=required, gap=gap)

    return EligibilityResult(
        status="ELIGIBLE",
        dataset=series.dataset,
        series_id=series.series_id,
        reason_code="OK",
        message="Clears minimum history, contiguity, and variance checks for the configured protocol.",
        observations=n,
        required_observations=required,
        frequency=series.frequency,
        season_length=m,
        largest_gap=gap,
        max_allowed_gap=config.MAX_ALLOWED_INTERNAL_GAP,
        config_version=config.CONFIG_VERSION,
        checked_rules=checks,
    )


def _refused(series, reason_code, message, checks, season_length,
             observations=None, required=None, gap=None) -> EligibilityResult:
    n = observations if observations is not None else len(series.records)
    return EligibilityResult(
        status="REFUSED",
        dataset=series.dataset,
        series_id=series.series_id,
        reason_code=reason_code,
        message=message,
        observations=n,
        required_observations=required if required is not None else config.required_observations(season_length or 1),
        frequency=series.frequency,
        season_length=season_length or 0,
        largest_gap=gap if gap is not None else 0,
        max_allowed_gap=config.MAX_ALLOWED_INTERNAL_GAP,
        config_version=config.CONFIG_VERSION,
        checked_rules=checks,
    )
