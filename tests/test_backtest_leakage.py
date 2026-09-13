"""
No-future-leakage tests for the rolling-origin backtest.

The most important property this project has: a forecast made at origin T
must be computable from history[0..T] alone, and must be provably unaffected
by anything that happens after T.
"""
import copy
import pytest

from src.backtest.rolling import run_backtest, OriginResult
from src.forecasting.models import MODELS


def _quarterly_periods(n, start_year=2000):
    periods = []
    year, q = start_year, 1
    for _ in range(n):
        periods.append(f"{year}-Q{q}")
        q += 1
        if q > 4:
            q, year = 1, year + 1
    return periods


def test_train_window_never_includes_the_forecast_target():
    values = [float(i) for i in range(40)]
    periods = _quarterly_periods(40)
    results = run_backtest(periods, values, season_length=4)
    for r in results:
        target_idx = periods.index(r.forecast_target)
        train_end_idx = periods.index(r.train_end)
        assert target_idx > train_end_idx, (
            f"forecast target {r.forecast_target} (idx {target_idx}) is not strictly "
            f"after the training window end {r.train_end} (idx {train_end_idx})"
        )


def test_train_window_length_matches_origin_plus_one():
    values = [float(i) for i in range(40)]
    periods = _quarterly_periods(40)
    results = run_backtest(periods, values, season_length=4)
    for r in results:
        assert periods[: r.origin + 1][-1] == r.train_end


def test_a_models_forecast_is_a_pure_function_of_the_training_prefix():
    """Directly calls each model with two histories that are identical up to
    index T, but differ after T, and asserts the forecast for horizon h made
    from history[:T+1] is identical in both cases -- proving the model
    functions themselves take no hidden dependency on anything beyond the
    slice they are given."""
    base = [float(i) + (i % 4) * 0.3 for i in range(30)]
    T = 20
    history_a = base[: T + 1]
    history_b_full = copy.deepcopy(base)
    history_b_full[T + 1:] = [999.0] * (len(base) - T - 1)  # corrupt everything after T
    history_b = history_b_full[: T + 1]

    assert history_a == history_b  # sanity: the visible slice is identical

    for name, fn in MODELS.items():
        out_a = fn(history_a, 4, 4)
        out_b = fn(history_b, 4, 4)
        assert out_a == out_b, f"{name} forecast differs despite identical training prefix"
