#!/usr/bin/env python3
"""
The core pipeline, run once per series per cycle:

    load processed series
        -> eligibility gate
            REFUSED  -> record refusal in the ledger, stop
            ELIGIBLE -> rolling-origin backtest
                     -> deterministic model selection
                     -> fit winner on full history, forecast h=1 ahead
                     -> build + seal the forecast contract
                     -> append to the ledger

Idempotent: re-running against unchanged data seals nothing new (the
forecast_id, built from series_id + forecast_origin + target_period, and
the ledger's own duplicate-hash guard, both prevent it).

Usage:
    python scripts/build.py [--code-version SHA]
"""
import _pathfix  # noqa: F401
import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from src import config
from src.data.eurostat import TidySeries
from src.eligibility.gate import evaluate
from src.backtest.rolling import run_backtest, summarize_by_model
from src.backtest.selection import select_model
from src.forecasting.models import MODELS
from src.ledger.contract import hash_values
from src.ledger.store import LedgerStore

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
LEDGER_PATH = ROOT / "data" / "ledger" / "ledger.jsonl"
SEALED_DIR = ROOT / "data" / "sealed"
BACKTEST_DIR = ROOT / "data" / "processed"


def load_series(key: str) -> TidySeries:
    doc = json.loads((PROCESSED_DIR / f"{key}.json").read_text(encoding="utf-8"))
    return TidySeries(
        dataset=doc["dataset"], series_id=doc["series_id"], geo=doc["geo"], unit=doc["unit"],
        frequency=doc["frequency"], dataset_updated=doc["dataset_updated"], fetched_at=doc["fetched_at"],
        records=doc["records"],
    )


def git_short_sha() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, timeout=5)
        sha = out.stdout.strip()
        return sha if sha else "dev"
    except Exception:
        return "dev"


def build_one(key: str, code_version: str, store: LedgerStore) -> dict:
    spec = config.SERIES[key]
    series = load_series(key)
    result = {"key": key, "series_id": series.series_id}

    eligibility = evaluate(series)
    result["eligibility"] = eligibility.to_dict()

    if eligibility.status == "REFUSED":
        store.record_refusal(eligibility.to_dict(), series.dataset, series.series_id)
        result["outcome"] = "REFUSED"
        print(f"[{key}] REFUSED: {eligibility.reason_code} -- {eligibility.message}")
        return result

    periods, values = series.periods(), series.values()
    m = eligibility.season_length

    backtest_results = run_backtest(periods, values, m)
    summary = summarize_by_model(backtest_results)
    mase_by_model = {name: summary[name]["mase"] for name in config.MODEL_NAMES if name in summary}
    selection = select_model(mase_by_model)
    selection["n_origins"] = summary[selection["winner"]]["n_origins"]

    (BACKTEST_DIR / f"{key}_backtest.json").write_text(json.dumps({
        "series_id": series.series_id,
        "season_length": m,
        "results": [r.to_dict() for r in backtest_results],
        "summary_by_model": summary,
        "selection": selection,
    }, indent=2), encoding="utf-8")

    winner = selection["winner"]
    forecast_origin = periods[-1]
    target_period = _next_period(forecast_origin, series.frequency)
    forecast_id = f"{series.series_id}::{forecast_origin}_to_{target_period}"

    already = store.find_sealed(forecast_id)
    if already is not None:
        result["outcome"] = "ALREADY_SEALED"
        result["forecast_id"] = forecast_id
        result["selection"] = selection
        print(f"[{key}] ELIGIBLE -> {forecast_id} already sealed (idempotent no-op).")
        return result

    forecast_values = MODELS[winner](values, config.MAX_HORIZON, m)
    point_forecast = forecast_values[0]  # h=1: the forward forecast for the next release

    model_parameters = ({"alpha": config.HOLT_ALPHA, "beta": config.HOLT_BETA} if winner == "Holt"
                         else {"season_length": m} if winner == "SeasonalNaive" else {})

    contract = {
        "forecast_id": forecast_id,
        "dataset": series.dataset,
        "series_id": series.series_id,
        "geo": series.geo,
        "unit": series.unit,
        "data_vintage": series.dataset_updated,
        "fetched_at": series.fetched_at,
        "forecast_origin": forecast_origin,
        "target_period": target_period,
        "horizon": 1,
        "model": winner,
        "model_parameters": model_parameters,
        "training_window_start": periods[0],
        "training_window_end": forecast_origin,
        "training_observation_count": len(values),
        "backtest_mase": mase_by_model[winner],
        "eligibility_status": eligibility.status,
        "eligibility_reason_code": eligibility.reason_code,
        "point_forecast": point_forecast,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_version": code_version,
        "config_version": config.CONFIG_VERSION,
        "input_data_hash": hash_values(values),
    }

    sealed_event = store.seal(contract, config.CONFIG_VERSION)
    safe_name = re.sub(r'[^A-Za-z0-9_.-]', '_', forecast_id)
    (SEALED_DIR / f"{safe_name}.json").write_text(
        json.dumps(sealed_event, indent=2), encoding="utf-8"
    )

    result["outcome"] = "SEALED"
    result["forecast_id"] = forecast_id
    result["selection"] = selection
    print(f"[{key}] ELIGIBLE -> selected {winner} (MASE={mase_by_model[winner]:.4f}, "
          f"origins={selection['n_origins']}) -> forecast {target_period} = {point_forecast:.3f} sealed")
    return result


def _next_period(period: str, frequency: str) -> str:
    if frequency == "annual":
        return str(int(period) + 1)
    year, q = period.split("-Q")
    year, q = int(year), int(q)
    q += 1
    if q > 4:
        q = 1
        year += 1
    return f"{year}-Q{q}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code-version", default=None)
    args = ap.parse_args()
    code_version = args.code_version or git_short_sha()

    store = LedgerStore(LEDGER_PATH)
    results = []
    for key in config.SERIES:
        results.append(build_one(key, code_version, store))

    print(f"\ncode_version={code_version} config_version={config.CONFIG_VERSION}")


if __name__ == "__main__":
    main()
