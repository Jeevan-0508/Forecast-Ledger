# Getting started

## Run the generated site

The hosted page is a static rendering of `site/data.json`, which is built from the processed data and append-only ledger artifacts.

```bash
python3 -m http.server 4173
```

Open `http://localhost:4173/`.

## Rebuild the data products

```bash
python3 scripts/build.py
python3 scripts/build_site_data.py
python3 scripts/verify.py
```

The exact workflow and ordering are defined in `SPEC.md` and `METHODOLOGY.md`. Do not edit the generated site data by hand.

## Run the test suite

```bash
pytest
```

The tests cover eligibility gates, anti-cheating/backtest leakage, model selection, grading, ledger storage and verification, Eurostat parsing, MASE, and forecast contracts.
