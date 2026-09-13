import pytest
from src.forecasting.models import naive, seasonal_naive, drift, holt


def test_naive_flat_continuation():
    assert naive([1, 2, 3, 4], 3) == [4, 4, 4]


def test_seasonal_naive_repeats_same_season():
    # quarterly, m=4: history = Q1..Q8 as 1..8; forecasting the next 4
    # quarters should repeat quarters 5..8 (the most recent full cycle)
    history = [1, 2, 3, 4, 5, 6, 7, 8]
    out = seasonal_naive(history, 4, 4)
    assert out == [5, 6, 7, 8]


def test_seasonal_naive_degenerates_to_naive_when_m_1():
    history = [10, 20, 30]
    assert seasonal_naive(history, 3, 1) == naive(history, 3)


def test_drift_extrapolates_average_slope():
    history = [0, 2, 4, 6]  # slope = (6-0)/3 = 2
    out = drift(history, 3)
    assert out == pytest.approx([8, 10, 12])


def test_drift_single_point_flat():
    assert drift([5], 2) == [5, 5]


def test_holt_flat_series_forecasts_flat():
    history = [10.0] * 10
    out = holt(history, 3)
    assert out == pytest.approx([10.0, 10.0, 10.0], abs=1e-9)


def test_holt_returns_requested_horizon_length():
    history = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert len(holt(history, 4)) == 4
