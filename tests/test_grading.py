from src.data.eurostat import TidySeries
from src.grading.grade import try_grade_outstanding
from src.ledger.store import LedgerStore


def _series(records):
    return TidySeries(dataset="ds", series_id="sid", geo="EU", unit="X",
                       frequency="quarterly", dataset_updated="2026-09-13T00:00:00Z",
                       fetched_at="t", records=records)


def _contract(fid, target_period, point_forecast):
    return {"forecast_id": fid, "dataset": "ds", "series_id": "sid",
            "target_period": target_period, "point_forecast": point_forecast, "model": "Drift"}


def test_grades_when_outcome_now_exists(tmp_path):
    store = LedgerStore(tmp_path / "ledger.jsonl")
    store.seal(_contract("sid::2026-Q2_to_2026-Q3", "2026-Q3", 105.0), "v1")

    series = _series([{"period": "2026-Q1", "value": 100.0},
                       {"period": "2026-Q2", "value": 102.0},
                       {"period": "2026-Q3", "value": 103.5}])
    newly = try_grade_outstanding(store, series, "v1")
    assert len(newly) == 1
    assert newly[0]["actual"] == 103.5
    assert newly[0]["signed_error"] == 103.5 - 105.0


def test_does_not_grade_when_outcome_absent(tmp_path):
    store = LedgerStore(tmp_path / "ledger.jsonl")
    store.seal(_contract("sid::2026-Q2_to_2026-Q3", "2026-Q3", 105.0), "v1")

    series = _series([{"period": "2026-Q1", "value": 100.0},
                       {"period": "2026-Q2", "value": 102.0}])  # Q3 not published yet
    newly = try_grade_outstanding(store, series, "v1")
    assert newly == []
    assert store.outstanding_forecasts() == ["sid::2026-Q2_to_2026-Q3"]


def test_original_forecast_unchanged_after_grading(tmp_path):
    store = LedgerStore(tmp_path / "ledger.jsonl")
    sealed = store.seal(_contract("sid::2026-Q2_to_2026-Q3", "2026-Q3", 105.0), "v1")
    series = _series([{"period": "2026-Q3", "value": 103.5}])
    try_grade_outstanding(store, series, "v1")

    still_sealed = store.find_sealed("sid::2026-Q2_to_2026-Q3")
    assert still_sealed["contract"] == sealed["contract"]
    assert still_sealed["hash"] == sealed["hash"]


def test_rerunning_grading_is_idempotent(tmp_path):
    store = LedgerStore(tmp_path / "ledger.jsonl")
    store.seal(_contract("sid::2026-Q2_to_2026-Q3", "2026-Q3", 105.0), "v1")
    series = _series([{"period": "2026-Q3", "value": 103.5}])
    try_grade_outstanding(store, series, "v1")
    newly_second_run = try_grade_outstanding(store, series, "v1")
    assert newly_second_run == []
    assert len([e for e in store.read_all() if e["event"] == "GRADED"]) == 1
