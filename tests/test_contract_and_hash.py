import copy
from src.ledger.contract import canonicalize, seal_hash, hash_values


def _contract():
    return {
        "forecast_id": "sid::2026-Q2_to_2026-Q3",
        "dataset": "sts_trtu_q",
        "series_id": "sid",
        "point_forecast": 105.277,
        "model": "Drift",
        "model_parameters": {},
        "created_at": "2026-09-13T00:00:00+00:00",
    }


def test_canonicalization_is_order_independent():
    c1 = _contract()
    c2 = {k: c1[k] for k in reversed(list(c1.keys()))}
    assert canonicalize(c1) == canonicalize(c2)


def test_hash_is_deterministic():
    c = _contract()
    assert seal_hash(c) == seal_hash(copy.deepcopy(c))


def test_hash_changes_after_any_field_mutation():
    c = _contract()
    h1 = seal_hash(c)
    c2 = copy.deepcopy(c)
    c2["point_forecast"] = c2["point_forecast"] + 0.001
    h2 = seal_hash(c2)
    assert h1 != h2


def test_hash_changes_after_created_at_mutation_only():
    c = _contract()
    h1 = seal_hash(c)
    c2 = copy.deepcopy(c)
    c2["created_at"] = "2099-01-01T00:00:00+00:00"
    assert seal_hash(c2) != h1


def test_hash_values_deterministic():
    assert hash_values([1.0, 2.0, 3.0]) == hash_values([1.0, 2.0, 3.0])
    assert hash_values([1.0, 2.0, 3.0]) != hash_values([1.0, 2.0, 3.1])
