import pytest
from src.backtest.metrics import in_sample_scale, scaled_error, mase, mae, MASEUndefined


def test_in_sample_scale_basic():
    train = [1, 2, 3, 4, 5]  # m=1 -> mean(|1|,|1|,|1|,|1|) = 1
    assert in_sample_scale(train, 1) == pytest.approx(1.0)


def test_in_sample_scale_too_short_raises():
    with pytest.raises(ValueError):
        in_sample_scale([1, 2], 4)


def test_scaled_error_zero_denominator_zero_numerator_is_zero():
    train = [5, 5, 5, 5]
    assert scaled_error(5, 5, train, 1) == 0.0


def test_scaled_error_zero_denominator_nonzero_numerator_undefined():
    train = [5, 5, 5, 5]
    with pytest.raises(MASEUndefined):
        scaled_error(6, 5, train, 1)


def test_scaled_error_normal_case():
    train = [1, 2, 3, 4, 5]  # scale = 1
    assert scaled_error(7, 6, train, 1) == pytest.approx(1.0)


def test_mase_averages_scaled_errors():
    assert mase([1.0, 2.0, 3.0]) == pytest.approx(2.0)


def test_mase_empty_raises():
    with pytest.raises(ValueError):
        mase([])


def test_mae_basic():
    assert mae([1.0, 2.0, 3.0]) == pytest.approx(2.0)


def test_mae_empty_raises():
    with pytest.raises(ValueError):
        mae([])
