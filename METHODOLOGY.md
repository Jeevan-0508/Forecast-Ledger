# Methodology

## Why rolling-origin, not a single train/test split

A single split tests one forecast made at one moment. Sliding the origin forward through the whole
series and re-forecasting at every valid point tests the *method* across many independent forecasting
occasions, which is the only way to say something honest about how it would have performed if it had
been running for real.

At each origin `T`, the model is given `history[0..T]` only. The observation at `T+h` is never touched
before the forecast for horizon `h` is produced — see `src/backtest/rolling.py`, and
`tests/test_backtest_leakage.py` / `tests/test_anti_cheating.py` for the tests that enforce this
structurally rather than by convention.

## Why MASE

MAPE flatters smooth series and is undefined or explosive near zero. MASE (Hyndman & Koehler, 2006)
scales the absolute forecast error against the in-sample mean absolute error of a naive (or seasonal
naive) forecaster, computed **only from the training window available at that origin**. That makes it
comparable across series of different scale and frequency, and ties the "is this good" question to "is
this better than the simplest possible alternative," not to an arbitrary percentage.

Implemented in `src/backtest/metrics.py`, unit-tested in `tests/test_mase.py`, including the zero-
denominator case: a perfectly flat training window scores 0 error if the actual is also flat, and is
explicitly flagged `MASEUndefined` (excluded from the aggregate, and counted) if the actual departs from
a flat training window. It is never silently coerced to infinity or zero.

## Why these four baselines, and no more

Naive, seasonal naive, drift, and Holt (double exponential smoothing) are transparent, auditable by
hand, and fast enough to refit at every rolling origin without hidden approximation. The Holt smoothing
constants are fixed (not optimised per series or per origin — see `src/config.py` for why: tuning them
against a training window is itself a hindsight-shaped decision, since the "best" constants depend on
how that window's future actually unfolded). None of this project's intellectual content is in model
sophistication. It is in the accounting around the forecast: what was known, when, and whether it should
have been made at all.

## Why refuse forecasts

Producing a number is easy. Defending one requires enough independent history to have actually tested
the method being used to produce it. `src/eligibility/gate.py` checks, in order: a known frequency, a
minimum observation count, contiguous history, and non-degenerate variance. The observation-count rule is
the one that matters here, and it is derived, not chosen to make any particular dataset fail:

- `MIN_TRAIN` = 2 full seasonal cycles (so Holt's level/trend fit isn't dominated by initial-condition
  noise), floored at 8 observations so an annual series (season length 1) can't "qualify" on 2 points.
- `MAX_HORIZON` = 4 periods ahead, fixed once at the product level for every series, not tuned per
  dataset.
- The backtest itself uses every valid *overlapping* rolling origin, which is standard practice once
  there is enough data. But overlap correlates adjacent errors, so it's too generous a bar for the
  eligibility *decision*. Eligibility instead asks whether there are at least 8 **non-overlapping**
  4-step windows, a conventional floor for treating a sample of errors as more than noise:
  `MIN_TEST_OBSERVATIONS` = 8 windows × 4 steps = 32.
- `required_observations` = `MIN_TRAIN` + `MIN_TEST_OBSERVATIONS` = 40 (with `MIN_TRAIN` = 8 for
  the datasets in this project).

This rule is dataset-agnostic: it would refuse *any* series with fewer than 40 usable observations,
regardless of subject, and would pass any series with 40 or more. It happens to refuse the German road
freight series (27 annual observations, 1999–2025) and pass the EU27 retail volume series (106 quarterly
observations). That is the honest result of applying one fixed rule, not a rule built backwards from the
desired demo outcome — see `tests/test_eligibility.py::test_exactly_enough_history_is_not_falsely_refused`
for the check that guards against exactly that failure mode.

## What sealing proves, and what it does not

Sealing canonicalizes the forecast contract (sorted keys, no incidental whitespace) and computes its
SHA-256. The hash, the contract, and a timestamp are appended to `data/ledger/ledger.jsonl`, which is
opened only in append mode by this codebase; nothing here ever rewrites an existing line.

**A cryptographic seal proves record integrity: this exact forecast, in this exact form, existed at this
point in the ledger's history, before the outcome was known.** Combined with the repository's own commit
history, that's a durable, checkable claim.

**It does not prove forecast quality.** A wrong forecast is preserved exactly as faithfully as a right
one. Quality is what the backtest MASE and the eventual graded error speak to — separately, and after
the fact.

## Data revisions

Official statistics get revised. This project distinguishes **forecast input vintage** (the Eurostat
`updated` timestamp captured in the contract at seal time) from **outcome observation vintage** (the
`updated` timestamp captured at grading time), and stores both. If Eurostat revises a value after it has
already been used to grade a forecast, this project does **not** silently re-grade: the original graded
outcome is permanent, by the same append-only principle as everything else. A later re-fetch that finds a
different value for an already-graded period is presently just not re-graded — it is not compared,
flagged, or reconciled against the original. This is an honest limitation, not a designed feature: full
revision tracking (storing every vintage seen for a period) would need a durable per-period version
history this project does not build, because Eurostat's own API does not expose a clean vintage history
for these series either.

## Reproducing this repository's results

```
pip install -r requirements.txt
pytest -q                       # 59 tests, none depend on network access
python scripts/fetch.py         # pulls fresh data (or reuses data/raw/ cache)
python scripts/build.py         # eligibility -> backtest -> selection -> seal
python scripts/grade.py         # grades any outstanding forecast whose outcome now exists
python scripts/verify.py        # independent ledger integrity check
python scripts/build_site_data.py
```

Re-running `build.py` and `grade.py` against unchanged data is a no-op (see
`tests/test_ledger_store.py` and `tests/test_grading.py`): idempotency is enforced by the ledger itself,
not by "don't run it twice."
