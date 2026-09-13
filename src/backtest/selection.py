"""
Model selection: pick the model with the lowest backtest MASE. Ties are
broken by a fixed priority order (src.config.MODEL_NAMES), never by
re-inspecting anything about how the future turned out.
"""
from __future__ import annotations

from src import config

TIE_EPSILON = 1e-9


def select_model(mase_by_model: dict) -> dict:
    """`mase_by_model`: {model_name: mase_or_None}. Models with MASE=None
    (no valid backtest points) are ineligible for selection. Returns a
    record describing the winner and the deterministic rule applied."""
    candidates = {k: v for k, v in mase_by_model.items() if v is not None}
    if not candidates:
        raise ValueError("no model produced a defined MASE; cannot select")

    best_mase = min(candidates.values())
    tied = [m for m in config.MODEL_NAMES
            if m in candidates and abs(candidates[m] - best_mase) <= TIE_EPSILON]
    # config.MODEL_NAMES is already the fixed priority order, so the first
    # entry that is tied for best is the deterministic winner.
    winner = tied[0]

    return {
        "candidate_models": list(mase_by_model.keys()),
        "mase_by_model": mase_by_model,
        "winner": winner,
        "selection_rule": "minimum backtest MASE",
        "tie_breaking_rule": f"fixed priority order {config.MODEL_NAMES}, first match wins",
        "tied_candidates": tied,
    }
