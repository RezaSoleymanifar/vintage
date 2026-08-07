"""The factor attribution, checked against data whose answer is known.

The only honest way to test a regression is to build a series with a planted
alpha and beta and see whether the estimator finds them back, standard errors
and all.
"""

import numpy as np
import pandas as pd

from vintage.engine import benchmark

TRUE_ALPHA = 0.004
TRUE_BETA = 0.8


def _planted(n: int = 240, noise: float = 0.02, seed: int = 0):
    """A strategy that is, by construction, TRUE_ALPHA + TRUE_BETA * market."""
    rng = np.random.default_rng(seed)
    index = pd.date_range("2005-01-31", periods=n, freq="ME")
    market = rng.normal(0.007, 0.045, n)
    strategy = TRUE_ALPHA + TRUE_BETA * market + rng.normal(0, noise, n)
    return (
        pd.Series(strategy, index=index),
        pd.DataFrame({"Mkt-RF": market}, index=index),
    )


def test_recovers_the_planted_beta():
    """Within three standard errors of the truth, which is the only claim an
    estimate on 240 noisy months can actually support."""
    strategy, factors = _planted()
    result = benchmark.compare(strategy, factors)

    beta = result["betas"]["Mkt-RF"]
    standard_error = abs(beta / result["beta_t_stats"]["Mkt-RF"])
    assert abs(beta - TRUE_BETA) < 3 * standard_error
    assert result["beta_t_stats"]["Mkt-RF"] > 10


def test_alpha_carries_a_t_stat_and_a_standard_error():
    strategy, factors = _planted()
    result = benchmark.compare(strategy, factors)
    assert result["alpha_standard_error"] > 0
    ratio = result["alpha_monthly"] / result["alpha_standard_error"]
    assert result["alpha_t_stat"] == pytest_approx(ratio, 0.01)


def test_the_t_stat_is_calibrated_on_pure_noise():
    """With no planted alpha, |t| should clear 2.0 about 5% of the time.

    Asserting that one particular seed comes back insignificant is the wrong
    test: seed 7 genuinely produces t = -2.05, and a t-statistic that never
    fired a false positive would be broken, not trustworthy. What has to hold
    is the rate.
    """
    n, trials = 360, 200
    false_positives = 0
    for seed in range(trials):
        rng = np.random.default_rng(seed)
        index = pd.date_range("1995-01-31", periods=n, freq="ME")
        market = rng.normal(0.007, 0.045, n)
        strategy = TRUE_BETA * market + rng.normal(0, 0.02, n)
        result = benchmark.compare(
            pd.Series(strategy, index=index),
            pd.DataFrame({"Mkt-RF": market}, index=index),
        )
        if abs(result["alpha_t_stat"]) > 2.0:
            false_positives += 1

    rate = false_positives / trials
    assert 0.01 < rate < 0.12, f"false positive rate {rate:.1%}, expected about 5%"


def test_degrees_of_freedom_account_for_every_estimated_coefficient():
    strategy, factors = _planted(n=120)
    factors["SMB"] = np.random.default_rng(3).normal(0, 0.02, 120)
    result = benchmark.compare(strategy, factors)
    # 120 months, three coefficients estimated: intercept, Mkt-RF, SMB.
    assert result["degrees_of_freedom"] == result["months_compared"] - 3


def test_short_overlap_refuses_rather_than_guessing():
    index = pd.date_range("2020-01-31", periods=6, freq="ME")
    result = benchmark.compare(
        pd.Series([0.01] * 6, index=index),
        pd.DataFrame({"Mkt-RF": [0.01] * 6}, index=index),
    )
    assert "error" in result


def pytest_approx(value: float, rel: float) -> object:
    import pytest

    return pytest.approx(value, rel=rel)
