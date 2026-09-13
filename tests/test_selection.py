from src.backtest.selection import select_model
from src import config


def test_selects_lowest_mase():
    result = select_model({"Naive": 0.9, "SeasonalNaive": 1.2, "Drift": 0.7, "Holt": 1.0})
    assert result["winner"] == "Drift"


def test_deterministic_tie_break_uses_fixed_priority_order():
    result = select_model({"Naive": 0.8, "SeasonalNaive": 0.8, "Drift": 0.9, "Holt": 0.95})
    assert result["winner"] == "Naive"  # first in config.MODEL_NAMES among the tied
    assert set(result["tied_candidates"]) == {"Naive", "SeasonalNaive"}


def test_ignores_undefined_mase_candidates():
    result = select_model({"Naive": None, "SeasonalNaive": 0.8, "Drift": None, "Holt": 1.0})
    assert result["winner"] == "SeasonalNaive"


def test_raises_if_no_candidate_has_a_defined_mase():
    import pytest
    with pytest.raises(ValueError):
        select_model({m: None for m in config.MODEL_NAMES})


def test_selection_is_reproducible():
    inp = {"Naive": 0.85, "SeasonalNaive": 1.22, "Drift": 0.71, "Holt": 1.01}
    r1 = select_model(dict(inp))
    r2 = select_model(dict(inp))
    assert r1 == r2
