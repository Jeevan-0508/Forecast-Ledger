"""
MASE (Mean Absolute Scaled Error), implemented and tested explicitly -- not
imported from a library we would otherwise have to trust blindly.

MASE(scaled error) for a single out-of-sample point:
    scaled_error = |actual - forecast| / scale
    scale = mean(|train[i] - train[i - m]| for i in [m, len(train)))
          -- the in-sample mean absolute error of a same-model-family naive
             (seasonal, period m) forecaster, computed ONLY from the training
             window available at that origin. Never from future data.

This module returns individual scaled errors (with explicit handling for the
degenerate/undefined cases) so callers can aggregate as needed; it never
silently averages away a bad case.
"""
from __future__ import annotations

from typing import Optional


class MASEUndefined(Exception):
    """Raised when the in-sample scale is zero and the numerator is not,
    i.e. the training window was perfectly constant but the actual
    departed from it. MASE has no finite value in this case."""


def in_sample_scale(train: list, season_length: int) -> float:
    m = max(season_length, 1)
    if len(train) <= m:
        raise ValueError(
            f"training window of {len(train)} observations is too short to "
            f"compute an in-sample scale at season length {m} "
            f"(needs > {m} observations)"
        )
    diffs = [abs(train[i] - train[i - m]) for i in range(m, len(train))]
    return sum(diffs) / len(diffs)


def scaled_error(actual: float, forecast: float, train: list, season_length: int) -> Optional[float]:
    """Returns the scaled absolute error, or 0.0 if both numerator and
    denominator are zero (a perfectly flat series correctly forecast flat is
    zero error, not undefined). Raises MASEUndefined if the denominator is
    zero but the numerator is not (no finite scale exists to judge the
    error against)."""
    scale = in_sample_scale(train, season_length)
    numerator = abs(actual - forecast)
    if scale == 0.0:
        if numerator == 0.0:
            return 0.0
        raise MASEUndefined(
            "in-sample scale is zero (constant training window) but the "
            "actual observation differs from the forecast; MASE is undefined "
            "for this origin."
        )
    return numerator / scale


def mase(scaled_errors: list) -> float:
    """Mean of a list of already-computed scaled errors. Callers are
    responsible for excluding any MASEUndefined origins and documenting how
    many were excluded (see backtest/rolling.py)."""
    if not scaled_errors:
        raise ValueError("cannot compute MASE from an empty list of scaled errors")
    return sum(scaled_errors) / len(scaled_errors)


def mae(errors_abs: list) -> float:
    if not errors_abs:
        raise ValueError("cannot compute MAE from an empty list")
    return sum(errors_abs) / len(errors_abs)
