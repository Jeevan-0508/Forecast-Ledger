"""
Four baseline forecasters. Every function takes only `history` (observations
up to and including the forecast origin) and returns forecasts for
h = 1..max_horizon. None of them, ever, may see anything past the origin.
"""
from __future__ import annotations

from src import config


def naive(history: list, max_horizon: int) -> list:
    """Flat continuation of the last observed value."""
    last = history[-1]
    return [last for _ in range(1, max_horizon + 1)]


def seasonal_naive(history: list, max_horizon: int, season_length: int) -> list:
    """Repeats the value from the same point in the last full season. Falls
    back to plain naive if season_length is 1 (annual data: no sub-period
    seasonality, so this is mathematically identical to naive, not a
    separate model in disguise -- documented, not hidden)."""
    m = max(season_length, 1)
    n = len(history)
    out = []
    for h in range(1, max_horizon + 1):
        k = -(-h // m)          # ceil(h / m): how many full seasons back we must reach
        idx = n + h - k * m - 1  # index into history of "same season, k cycles ago"
        out.append(history[idx])
    return out


def drift(history: list, max_horizon: int) -> list:
    """Random walk with drift: extrapolates the average slope between the
    first and last observed point."""
    n = len(history)
    if n < 2:
        return [history[-1] for _ in range(max_horizon)]
    slope = (history[-1] - history[0]) / (n - 1)
    return [history[-1] + h * slope for h in range(1, max_horizon + 1)]


def holt(history: list, max_horizon: int,
         alpha: float = config.HOLT_ALPHA, beta: float = config.HOLT_BETA) -> list:
    """Holt's linear (double exponential smoothing) method with fixed,
    un-tuned smoothing constants (see src/config.py for why they are not
    optimised per series)."""
    level = history[0]
    trend = history[1] - history[0] if len(history) > 1 else 0.0
    for y in history[1:]:
        prev_level = level
        level = alpha * y + (1 - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend
    return [level + h * trend for h in range(1, max_horizon + 1)]


MODELS = {
    "Naive": lambda history, max_horizon, season_length: naive(history, max_horizon),
    "SeasonalNaive": lambda history, max_horizon, season_length: seasonal_naive(history, max_horizon, season_length),
    "Drift": lambda history, max_horizon, season_length: drift(history, max_horizon),
    "Holt": lambda history, max_horizon, season_length: holt(history, max_horizon),
}
