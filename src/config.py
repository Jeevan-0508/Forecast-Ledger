"""
Single place for every threshold and constant used by the pipeline.

Nothing here was chosen to make a particular dataset pass or fail. Each
constant is derived from a stated methodological reason, documented next to
it and again in METHODOLOGY.md. If a dataset's outcome ever conflicts with
the reasoning, the reasoning is what gets changed, not the constant.
"""

CONFIG_VERSION = "protocol-v1"

# Forecast horizon, in native periods of the series. Fixed once at the
# product level (not tuned per dataset): every eligible series is evaluated
# and forecast on a "how far ahead can we responsibly say something"
# question of up to 4 steps, and a single forward forecast at h=1.
MAX_HORIZON = 4

# Seasonal naive / MASE need a season length. Derived from series frequency,
# not guessed: quarterly -> 4, monthly -> 12, annual -> 1 (no sub-period
# seasonality exists, so seasonal-naive degenerates to naive, which is
# correct, not a bug).
SEASON_LENGTH_BY_FREQUENCY = {
    "quarterly": 4,
    "monthly": 12,
    "annual": 1,
}

# Minimum training window before any model (in particular Holt, which fits
# a level and a trend, i.e. 2 free parameters) is trusted. Two full seasonal
# cycles is standard practice for double exponential smoothing; below that,
# level/trend initialisation dominates the fit. Floored at 8 so an annual
# series (season length 1) isn't allowed to "qualify" with 2 observations.
MIN_TRAIN_FLOOR = 8


def min_train(season_length: int) -> int:
    return max(2 * season_length, MIN_TRAIN_FLOOR)


# The backtest itself uses every valid rolling origin (overlapping windows),
# which is standard practice and efficient once we already trust there is
# enough history. But that overlap correlates adjacent errors, so it is too
# generous a bar for the ELIGIBILITY decision itself. For eligibility we ask
# a stricter question: are there enough *non-overlapping* horizon-length
# windows to see the model make MAX_HORIZON independent mistakes, repeatedly?
# 8 non-overlapping windows is the smallest sample size conventionally
# treated as enough to distinguish real accuracy from origin-to-origin noise.
MIN_INDEPENDENT_TEST_WINDOWS = 8

# Observations required purely to test on eligibility:
#   MIN_INDEPENDENT_TEST_WINDOWS non-overlapping windows of MAX_HORIZON steps
MIN_TEST_OBSERVATIONS = MIN_INDEPENDENT_TEST_WINDOWS * MAX_HORIZON


def required_observations(season_length: int) -> int:
    """Total usable observations needed to run the configured protocol:
    enough training history for the models, plus enough held-out
    observations to independently sample MAX_HORIZON-step errors
    MIN_INDEPENDENT_TEST_WINDOWS times over."""
    return min_train(season_length) + MIN_TEST_OBSERVATIONS


# Missingness: a series with internal gaps larger than this (in native
# periods) cannot supply a contiguous training window straddling the gap
# without interpolation, and this project does not interpolate silently.
MAX_ALLOWED_INTERNAL_GAP = 1  # one missing period tolerated as-is; more, refuse

# Freshness: data is required to have been fetched (not necessarily updated)
# within this many days of use, so a stale local cache doesn't quietly drive
# a forecast. This governs cache re-use in scripts/fetch.py.
MAX_CACHE_AGE_DAYS = 92  # ~one quarter, matching the automation cadence

# Fixed Holt smoothing constants. Not optimised per-origin or per-series:
# optimising them would itself be a hindsight-shaped decision (the "best"
# alpha/beta over a training window depends on how that window's future
# unfolded) and would need to be defended with as much rigour as the models
# themselves. Standard, moderate, un-tuned values are used everywhere.
HOLT_ALPHA = 0.3
HOLT_BETA = 0.1

MODEL_NAMES = ["Naive", "SeasonalNaive", "Drift", "Holt"]


# The two datasets this project touches, and exactly how each single series
# is pinned out of them. No other series are fetched by this project.
SERIES = {
    "retail_volume_eu27": {
        "dataset": "sts_trtu_q",
        "series_id": "sts_trtu_q.EU27_2020.G47.VOL_SLS.I21.SCA",
        "geo": "EU27_2020",
        "unit": "I21",
        "role": "forecastable",
        "description": "Retail trade volume of sales, EU27, index 2021=100, seasonally & calendar adjusted",
        "params": {
            "geo": "EU27_2020",
            "s_adj": "SCA",
            "nace_r2": "G47",
            "unit": "I21",
            "indic_bt": "VOL_SLS",
        },
    },
    "road_freight_de": {
        "dataset": "road_go_ta_tott",
        "series_id": "road_go_ta_tott.DE.TOTAL.TOTAL.MIO_TKM",
        "geo": "DE",
        "unit": "MIO_TKM",
        "role": "refusal_demo",
        "description": "Road freight transport, Germany, total, million tonne-kilometres, annual",
        "params": {
            "geo": "DE",
            "tra_type": "TOTAL",
            "tra_oper": "TOTAL",
            "unit": "MIO_TKM",
        },
    },
}
