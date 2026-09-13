"""
THE anti-cheating test.

Run the full backtest over a series. Record every prediction made at every
origin. Then mutate every observation strictly AFTER a chosen historical
origin T, re-run the backtest, and assert the prediction made AT origin T is
byte-for-byte identical in both runs, for every model.

If changing the future changes a past forecast, this test must fail loudly:
that would be the exact hindsight leak this entire project exists to make
structurally impossible.
"""
import copy
import random

from src.backtest.rolling import run_backtest


def _quarterly_periods(n, start_year=1995):
    periods = []
    year, q = start_year, 1
    for _ in range(n):
        periods.append(f"{year}-Q{q}")
        q += 1
        if q > 4:
            q, year = 1, year + 1
    return periods


def _predictions_at_origin(results, origin):
    return sorted(
        ((r.model, r.horizon, r.prediction) for r in results if r.origin == origin),
        key=lambda t: (t[0], t[1]),
    )


def test_mutating_the_future_never_changes_a_past_prediction():
    rng = random.Random(42)
    n = 50
    periods = _quarterly_periods(n)
    values = [50.0 + i * 0.7 + (i % 4) * 2.0 + rng.uniform(-0.5, 0.5) for i in range(n)]

    results_before = run_backtest(periods, values, season_length=4)

    chosen_origin = n // 2
    mutated = copy.deepcopy(values)
    for i in range(chosen_origin + 1, n):
        mutated[i] = mutated[i] * 7.0 + 1000.0  # violently different future

    results_after = run_backtest(periods, mutated, season_length=4)

    before = _predictions_at_origin(results_before, chosen_origin)
    after = _predictions_at_origin(results_after, chosen_origin)

    assert before == after, (
        "TEMPORAL LEAKAGE DETECTED: predictions made at an historical origin "
        "changed after future observations were mutated. A forecast must be "
        "a pure function of the data available at its own origin."
    )


def test_mutating_the_future_changes_only_later_predictions():
    """Complementary check: the mutation must actually be observable
    somewhere, at an origin whose training window includes the mutated
    region, otherwise the "no leakage" result above would be trivially true
    because nothing downstream even reacts to the data."""
    n = 50
    periods = _quarterly_periods(n)
    values = [50.0 + i * 0.7 + (i % 4) * 2.0 for i in range(n)]

    results_before = run_backtest(periods, values, season_length=4)

    chosen_origin = n // 2
    later_origin = n - 2
    mutated = copy.deepcopy(values)
    for i in range(chosen_origin + 1, n):
        mutated[i] = mutated[i] * 7.0 + 1000.0

    results_after = run_backtest(periods, mutated, season_length=4)

    before_later = _predictions_at_origin(results_before, later_origin)
    after_later = _predictions_at_origin(results_after, later_origin)
    assert before_later != after_later, (
        "expected the mutation to change predictions made at a later origin "
        "whose training window includes the mutated observations -- if it "
        "didn't, this test isn't actually exercising anything"
    )
