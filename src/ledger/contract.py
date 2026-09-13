"""
Forecast contract: the exact, complete record of what was known and decided
at the moment a forecast was made. Canonicalized and hashed so that any
later change to any field is detectable.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ForecastContract:
    forecast_id: str
    dataset: str
    series_id: str
    geo: str
    unit: str
    data_vintage: str            # dataset "updated" timestamp from Eurostat, as fetched
    fetched_at: str              # when this run pulled the data
    forecast_origin: str         # last observed period used as the base of the forecast
    target_period: str           # period being forecast
    horizon: int
    model: str
    model_parameters: dict
    training_window_start: str
    training_window_end: str
    training_observation_count: int
    backtest_mase: Optional[float]
    eligibility_status: str
    eligibility_reason_code: str
    point_forecast: float
    created_at: str
    code_version: str
    config_version: str
    input_data_hash: str

    def to_dict(self) -> dict:
        return asdict(self)


def canonicalize(contract_dict: dict) -> str:
    """Deterministic JSON: sorted keys, no incidental whitespace, ASCII
    only. Two contracts with identical field values always canonicalize to
    the identical string, regardless of dict construction order."""
    return json.dumps(contract_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def seal_hash(contract_dict: dict) -> str:
    canon = canonicalize(contract_dict)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def hash_values(values: list) -> str:
    """Content hash of an input data vector, used as `input_data_hash` so a
    contract can prove exactly which numbers it was computed from."""
    canon = json.dumps(values, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()
