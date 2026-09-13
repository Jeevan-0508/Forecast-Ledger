"""
Genuine rolling-origin backtest.

For every origin T with enough history:
    TRAIN = history[0 .. T]        (inclusive, everything up to and including T)
    for h in 1..MAX_HORIZON where T+h is still inside the observed series:
        FORECAST = model(TRAIN, h)
        ACTUAL   = history[T + h]

The model function is only ever given TRAIN. It is structurally impossible
for it to see ACTUAL from inside this loop, because ACTUAL is not sliced out
of `history` until after the forecast call returns.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from src import config
from src.backtest.metrics import scaled_error, MASEUndefined, mase, mae
from src.forecasting.models import MODELS


@dataclass
class OriginResult:
    origin: int              # index into the series (0-based) of the last training observation
    train_start: str
    train_end: str
    horizon: int
    forecast_target: str
    actual: float
    prediction: float
    error: float
    absolute_error: float
    model: str
    scaled_error: float = None   # None if MASEUndefined at this origin

    def to_dict(self):
        return asdict(self)


def run_backtest(periods: list, values: list, season_length: int,
                  models: list = None, max_horizon: int = None) -> list:
    """Returns a flat list of OriginResult across every (origin, horizon,
    model) combination. `periods` and `values` must already be
    chronologically ordered and aligned index-for-index."""
    if len(periods) != len(values):
        raise ValueError("periods and values must be the same length")
    models = models or config.MODEL_NAMES
    max_horizon = max_horizon or config.MAX_HORIZON
    n = len(values)
    min_train_n = config.min_train(season_length)

    results = []
    # Last valid training index is n-2 (need at least one future point);
    # first valid training index (0-based, inclusive) must contain
    # min_train_n observations, i.e. index min_train_n - 1.
    for t in range(min_train_n - 1, n - 1):
        train = values[: t + 1]
        for model_name in models:
            model_fn = MODELS[model_name]
            forecasts = model_fn(train, max_horizon, season_length)
            for h in range(1, max_horizon + 1):
                target_idx = t + h
                if target_idx >= n:
                    break
                actual = values[target_idx]
                prediction = forecasts[h - 1]
                err = actual - prediction
                try:
                    se = scaled_error(actual, prediction, train, season_length)
                except MASEUndefined:
                    se = None
                results.append(OriginResult(
                    origin=t,
                    train_start=periods[0],
                    train_end=periods[t],
                    horizon=h,
                    forecast_target=periods[target_idx],
                    actual=actual,
                    prediction=prediction,
                    error=err,
                    absolute_error=abs(err),
                    model=model_name,
                    scaled_error=se,
                ))
    return results


def summarize_by_model(results: list) -> dict:
    """Aggregate MASE (over non-undefined origins) and MAE per model, plus
    how many origins were excluded from MASE for being undefined."""
    by_model = {}
    for r in results:
        by_model.setdefault(r.model, {"scaled": [], "abs_errors": [], "undefined": 0, "origins": set()})
        bucket = by_model[r.model]
        bucket["abs_errors"].append(r.absolute_error)
        bucket["origins"].add(r.origin)
        if r.scaled_error is None:
            bucket["undefined"] += 1
        else:
            bucket["scaled"].append(r.scaled_error)

    summary = {}
    for model_name, bucket in by_model.items():
        summary[model_name] = {
            "mase": mase(bucket["scaled"]) if bucket["scaled"] else None,
            "mae": mae(bucket["abs_errors"]),
            "n_scored_points": len(bucket["abs_errors"]),
            "n_origins": len(bucket["origins"]),
            "n_mase_undefined": bucket["undefined"],
        }
    return summary
