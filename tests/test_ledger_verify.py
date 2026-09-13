from src.ledger.store import LedgerStore
from src.ledger.verify import verify


def _contract(fid="sid::2026-Q2_to_2026-Q3"):
    return {"forecast_id": fid, "dataset": "ds", "series_id": "sid",
            "target_period": "2026-Q3", "point_forecast": 100.0, "model": "Drift"}


def test_clean_ledger_verifies(tmp_path):
    store = LedgerStore(tmp_path / "ledger.jsonl")
    store.seal(_contract(), "v1")
    store.grade("sid::2026-Q2_to_2026-Q3", "2026-Q3", {"actual": 101.0}, "v1")
    report = verify(store.read_all())
    assert report["status"] == "VERIFIED"
    assert report["sealed_count"] == 1
    assert report["graded_count"] == 1


def test_tampered_contract_hash_detected_as_invalid(tmp_path):
    store = LedgerStore(tmp_path / "ledger.jsonl")
    store.seal(_contract(), "v1")
    events = store.read_all()
    events[0]["contract"]["point_forecast"] = 99999.0  # tamper after the fact, in memory
    report = verify(events)
    assert report["status"] == "INVALID"
    assert any("does not match" in i["message"] for i in report["issues"])


def test_graded_with_no_sealed_event_is_invalid():
    events = [{
        "event": "GRADED", "forecast_id": "ghost", "target_period": "2026-Q3",
        "graded_at": "2026-01-01T00:00:00", "config_version": "v1", "actual": 1.0,
    }]
    report = verify(events)
    assert report["status"] == "INVALID"
