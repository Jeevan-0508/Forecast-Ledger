import pytest
from src.ledger.store import LedgerStore, LedgerError


def _contract(fid="sid::2026-Q2_to_2026-Q3", point_forecast=105.0):
    return {
        "forecast_id": fid,
        "dataset": "sts_trtu_q",
        "series_id": "sid",
        "target_period": "2026-Q3",
        "point_forecast": point_forecast,
        "model": "Drift",
    }


def test_append_only_file_grows_and_never_shrinks(tmp_path):
    store = LedgerStore(tmp_path / "ledger.jsonl")
    store.seal(_contract(), "v1")
    size_after_one = (tmp_path / "ledger.jsonl").stat().st_size
    store.grade("sid::2026-Q2_to_2026-Q3", "2026-Q3", {"actual": 100.0}, "v1")
    size_after_two = (tmp_path / "ledger.jsonl").stat().st_size
    assert size_after_two > size_after_one


def test_sealing_the_identical_contract_twice_is_a_noop(tmp_path):
    store = LedgerStore(tmp_path / "ledger.jsonl")
    e1 = store.seal(_contract(), "v1")
    e2 = store.seal(_contract(), "v1")
    assert e1["hash"] == e2["hash"]
    events = store.read_all()
    assert len([e for e in events if e["event"] == "SEALED"]) == 1


def test_sealing_a_changed_contract_with_same_forecast_id_raises(tmp_path):
    store = LedgerStore(tmp_path / "ledger.jsonl")
    store.seal(_contract(), "v1")
    with pytest.raises(LedgerError):
        store.seal(_contract(point_forecast=999.0), "v1")


def test_duplicate_grading_is_rejected(tmp_path):
    store = LedgerStore(tmp_path / "ledger.jsonl")
    store.seal(_contract(), "v1")
    store.grade("sid::2026-Q2_to_2026-Q3", "2026-Q3", {"actual": 100.0}, "v1")
    with pytest.raises(LedgerError):
        store.grade("sid::2026-Q2_to_2026-Q3", "2026-Q3", {"actual": 101.0}, "v1")


def test_grading_wrong_target_period_rejected(tmp_path):
    store = LedgerStore(tmp_path / "ledger.jsonl")
    store.seal(_contract(), "v1")
    with pytest.raises(LedgerError):
        store.grade("sid::2026-Q2_to_2026-Q3", "2026-Q4", {"actual": 100.0}, "v1")


def test_grading_unknown_forecast_id_rejected(tmp_path):
    store = LedgerStore(tmp_path / "ledger.jsonl")
    with pytest.raises(LedgerError):
        store.grade("nonexistent", "2026-Q3", {"actual": 100.0}, "v1")


def test_outstanding_forecasts_excludes_graded(tmp_path):
    store = LedgerStore(tmp_path / "ledger.jsonl")
    store.seal(_contract(), "v1")
    assert store.outstanding_forecasts() == ["sid::2026-Q2_to_2026-Q3"]
    store.grade("sid::2026-Q2_to_2026-Q3", "2026-Q3", {"actual": 100.0}, "v1")
    assert store.outstanding_forecasts() == []


def test_repeated_refusal_recording_is_idempotent(tmp_path):
    store = LedgerStore(tmp_path / "ledger.jsonl")
    eligibility = {"reason_code": "INSUFFICIENT_HISTORY", "message": "no",
                   "observations": 27, "config_version": "v1"}
    store.record_refusal(eligibility, "road_go_ta_tott", "sid2")
    store.record_refusal(eligibility, "road_go_ta_tott", "sid2")
    events = [e for e in store.read_all() if e["event"] == "REFUSED"]
    assert len(events) == 1
