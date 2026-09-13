from src.data.eurostat import TidySeries
from src.eligibility.gate import evaluate
from src import config


def _series(n, frequency="quarterly", start_year=2000, gap_at=None, constant=False):
    records = []
    year, q = start_year, 1
    for i in range(n):
        period = f"{year}-Q{q}" if frequency == "quarterly" else str(year)
        if gap_at is not None and gap_at <= i < gap_at + 2:
            pass  # skip two consecutive observations: a gap of 2, which exceeds the 1-period tolerance
        else:
            val = 100.0 if constant else 100.0 + i
            records.append({"period": period, "value": val})
        if frequency == "quarterly":
            q += 1
            if q > 4:
                q = 1
                year += 1
        else:
            year += 1
    return TidySeries(dataset="ds", series_id="sid", geo="EU", unit="X",
                       frequency=frequency, dataset_updated=None, fetched_at="t", records=records)


def test_sufficient_quarterly_history_is_eligible():
    s = _series(config.required_observations(4) + 5, "quarterly")
    r = evaluate(s)
    assert r.status == "ELIGIBLE"
    assert r.reason_code == "OK"


def test_insufficient_annual_history_is_refused_with_real_numbers():
    s = _series(27, "annual")
    r = evaluate(s)
    assert r.status == "REFUSED"
    assert r.reason_code == "INSUFFICIENT_HISTORY"
    assert r.observations == 27
    assert r.required_observations == config.required_observations(1)
    assert r.required_observations > 27  # this is what actually makes it fail, not an arbitrary flag


def test_exactly_enough_history_is_not_falsely_refused():
    """The methodological floor, not a margin for comfort: exactly the
    required count must pass."""
    s = _series(config.required_observations(4), "quarterly")
    r = evaluate(s)
    assert r.status == "ELIGIBLE", (
        "a series meeting the documented required_observations() count must "
        "not be refused -- refusing it anyway would mean the threshold is "
        "aspirational rather than the actual rule being applied"
    )


def test_one_below_required_is_refused():
    s = _series(config.required_observations(4) - 1, "quarterly")
    r = evaluate(s)
    assert r.status == "REFUSED"
    assert r.reason_code == "INSUFFICIENT_HISTORY"


def test_large_internal_gap_refused_after_history_check_passes():
    n = config.required_observations(4) + 10
    s = _series(n, "quarterly", gap_at=n // 2)
    r = evaluate(s)
    assert r.status == "REFUSED"
    assert r.reason_code == "NON_CONTIGUOUS_HISTORY"


def test_constant_series_refused_as_degenerate():
    n = config.required_observations(4) + 5
    s = _series(n, "quarterly", constant=True)
    r = evaluate(s)
    assert r.status == "REFUSED"
    assert r.reason_code == "DEGENERATE_SERIES"


def test_unsupported_frequency_refused():
    s = _series(100, "quarterly")
    s.frequency = "weekly"
    r = evaluate(s)
    assert r.status == "REFUSED"
    assert r.reason_code == "UNSUPPORTED_FREQUENCY"


def test_refusal_is_reproducible():
    s = _series(27, "annual")
    r1 = evaluate(s)
    r2 = evaluate(s)
    assert r1.to_dict() == r2.to_dict()
