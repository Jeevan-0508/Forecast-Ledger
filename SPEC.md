# Forecast Ledger — build spec

Day-14 project of the 16-day sprint. Written 2026-09-13, to be built 2026-09-14.

## The one-line idea

Most forecasting demos report how well the model fits data it has already seen. This one **seals a
forecast before the answer exists, publishes the error when it arrives, and refuses to forecast a series
whose history cannot support one.**

## Why this project and not another scanner

- Three compliance scanners already exist (GDPR, EU AI Act, DORA). That family is saturated.
- The resume line *"forecasting engine ~95% accuracy"* has **no repo behind it**. Verified tonight: no
  repo in the portfolio does time-series forecasting or backtesting. `riskos` has Monte Carlo simulation,
  which is a different thing.
- The ethic — publish the error, refuse rather than guess — is the same one already carried by risk-swarm
  (withheld confidence) and fraud-watch (the refused-figures card). This extends the brand, it does not
  start a new one.

## Data — verified reachable 2026-09-13

Eurostat REST, no key, no auth:
`https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/<code>?format=JSON&lang=EN`

| Role | Code | Shape | Why |
|---|---|---|---|
| **Primary, forecastable** | `sts_trtu_q` | quarterly, **142 points, 1991-Q1 → 2026-Q2** | Wholesale and retail turnover and volume of sales. Long enough for a real rolling backtest, refreshes quarterly so a sealed forecast gets graded within ~3 months. Retail volume is the exposure base loss prevention scales against. |
| **Secondary, to be REFUSED** | `road_go_ta_tott` | annual, **27 points 1999 → 2025**, 37 geos, 67,673 values, updated 2026-07-30 | Road freight transport, t / tkm / vehicle-km. On-domain, and deliberately included because 27 annual points cannot support an honest interval. The tool publishes it as refused, with the reason. |

The thin dataset is not a weakness of the project. It is the demonstration.

Do NOT reuse `shrink-signal/data/crime.json`. Same data would make this look like a shrink-signal feature
rather than its own project.

## Scope — one day, deliberately small

1. `scripts/fetch.py` — pull both codes to `data/raw/`, flatten Eurostat JSON-stat into tidy
   `{series_id, geo, unit, period, value}`. Cache raw responses so a rebuild needs no network.
2. `scripts/forecast.py` — **four baselines only, no ML**: naive (last value), seasonal naive (same
   quarter last year), drift (linear trend), Holt linear. Anything fancier is out of scope and would
   invite a claim that cannot be defended.
3. `scripts/backtest.py` — rolling-origin evaluation. For every origin with enough history, forecast
   h = 1..4 and score against the actual. Report **MASE** (against seasonal naive) as the headline, MAE
   and MAPE alongside. MASE because a MAPE on its own flatters a smooth series.
4. **The eligibility gate** — a series is forecast only if it clears a minimum observation count and a
   non-degenerate variance check. Otherwise it is written to the output as `REFUSED` with the failing
   condition named. `road_go_ta_tott` must land here.
5. `scripts/seal.py` — writes `data/sealed/<iso-date>.json`: the forward forecast for the next release,
   with a content hash. **Append-only: a past seal is never rewritten.** A later run reads old seals,
   finds actuals that have since arrived, and grades them.
6. `index.html` — Tailwind CDN + Chart.js, matching the existing static-app pattern. Four panels:
   actual-vs-forecast chart, error table by horizon, the refusal list with reasons, and the seal ledger
   showing each sealed forecast as PENDING or GRADED with its realised error.
7. `.github/workflows/refresh.yml` — quarterly cron plus manual trigger: fetch, backtest, grade old
   seals, write a new seal, commit. Signal-driven and computation-only — it recomputes and reports, it
   never edits a past claim.
8. Tests, `pytest`: MASE denominator, MAPE zero-handling, the eligibility gate firing on the annual
   series, and the seal store rejecting a rewrite of an existing date.

## Out of scope, on purpose

ARIMA / Prophet / any neural model · confidence intervals from bootstrap · more than two datasets ·
a live API push · country-by-country pages. If it starts growing, it stops.

## Definition of done

- [ ] Both datasets fetched and cached; rebuild works offline
- [ ] Backtest table populated from real actuals, no hand-written figures anywhere
- [ ] At least one series visibly REFUSED, with the reason on screen
- [ ] One seal written, and the grading path proven by a test with a back-dated seal
- [ ] Tests green; every number in the README grep-verified against the generated JSON
- [ ] README with the standard hero, brand banner, JK mark in the app header, screenshots
- [ ] MIT LICENSE as pure licence text; any data-attribution note goes in LICENSE-DATA
- [ ] Pushed, Pages enabled, description + topics set

## First move tomorrow

Run `fetch.py` against `sts_trtu_q` and look at the real numbers before writing a single line of the
forecaster. If the series turns out to be broken or too sparse per-geo, the fallback is `ei_bsin_q_r2`
(industry survey, **187 quarters, 1980-Q1 → 2026-Q3**, verified tonight).