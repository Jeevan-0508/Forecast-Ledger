import pytest
from src.data.eurostat import parse_jsonstat, largest_gap, missing_count, FetchError, TidySeries


def _doc(periods_values, freq="Q", updated="2026-09-12T11:00:00+0200"):
    time_index = {p: i for i, (p, v) in enumerate(periods_values)}
    return {
        "updated": updated,
        "dimension": {
            "freq": {"category": {"label": {freq: "x"}}},
            "time": {"category": {"index": time_index}},
        },
        "value": {str(i): v for i, (p, v) in enumerate(periods_values) if v is not None},
    }


def test_parses_and_sorts_chronologically():
    doc = _doc([("2000-Q2", 2.0), ("2000-Q1", 1.0), ("2000-Q3", 3.0)])
    s = parse_jsonstat(doc, "ds", "sid", "EU", "I21")
    assert s.periods() == ["2000-Q1", "2000-Q2", "2000-Q3"]
    assert s.values() == [1.0, 2.0, 3.0]


def test_annual_frequency_label():
    doc = _doc([("1999", 1.0), ("2000", 2.0)], freq="A")
    s = parse_jsonstat(doc, "ds", "sid", "DE", "MIO_TKM")
    assert s.frequency == "annual"


def test_missing_values_are_absent_not_zero():
    doc = _doc([("2000-Q1", 1.0), ("2000-Q2", None), ("2000-Q3", 3.0)])
    s = parse_jsonstat(doc, "ds", "sid", "EU", "I21")
    assert s.periods() == ["2000-Q1", "2000-Q3"]
    assert missing_count(s) == 1
    assert largest_gap(s) == 1


def test_colliding_time_index_positions_raise():
    doc = _doc([("2000-Q1", 1.0), ("2000-Q2", 2.0)])
    # Corrupt the response: two distinct period labels claim the same position.
    doc["dimension"]["time"]["category"]["index"]["2000-Q3"] = 0
    with pytest.raises(FetchError):
        parse_jsonstat(doc, "ds", "sid", "EU", "I21")


def test_multiple_freq_categories_rejected():
    doc = _doc([("2000-Q1", 1.0)])
    doc["dimension"]["freq"]["category"]["label"] = {"Q": "x", "A": "y"}
    with pytest.raises(FetchError):
        parse_jsonstat(doc, "ds", "sid", "EU", "I21")
