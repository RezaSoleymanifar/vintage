"""The deflation math is the whole trust story, so it gets the real tests."""

import math

import pytest

from vintage.engine import honesty


@pytest.fixture(autouse=True)
def clean_trial_log():
    honesty.reset_trials()
    yield
    honesty.reset_trials()


def test_norm_cdf_known_points():
    assert honesty.norm_cdf(0.0) == pytest.approx(0.5)
    assert honesty.norm_cdf(1.96) == pytest.approx(0.975, abs=1e-3)
    assert honesty.norm_cdf(-1.96) == pytest.approx(0.025, abs=1e-3)


def test_norm_ppf_inverts_norm_cdf():
    for p in (0.01, 0.1, 0.5, 0.9, 0.99):
        assert honesty.norm_cdf(honesty.norm_ppf(p)) == pytest.approx(p, abs=1e-4)


def test_norm_ppf_handles_degenerate_probabilities():
    assert honesty.norm_ppf(1.0) == math.inf
    assert honesty.norm_ppf(0.0) == -math.inf


def test_trial_log_counts_and_resets():
    assert honesty.trial_count() == 0
    honesty.record_trial({"signal": "momentum_12_1"}, 0.05)
    honesty.record_trial({"signal": "reversal_1m"}, 0.03)
    assert honesty.trial_count() == 2
    assert honesty.reset_trials() == 2
    assert honesty.trial_count() == 0


def test_expected_max_sharpe_rises_with_trial_count():
    few = honesty.expected_max_sharpe(5, 0.01)
    many = honesty.expected_max_sharpe(500, 0.01)
    assert 0 < few < many


def test_expected_max_sharpe_is_zero_without_trials_or_variance():
    assert honesty.expected_max_sharpe(1, 0.01) == 0.0
    assert honesty.expected_max_sharpe(50, 0.0) == 0.0


def test_more_trials_lower_the_deflated_probability():
    """The point of the module: asking forty times must cost you something."""
    kwargs = dict(sharpe=0.08, n_obs=2000, trial_sharpes=[0.02, 0.05, 0.08])
    honest = honesty.deflated_sharpe(trials=3, **kwargs)
    overfit = honesty.deflated_sharpe(trials=200, **kwargs)
    assert honest["deflated_sharpe_probability"] > overfit["deflated_sharpe_probability"]
    assert overfit["per_observation_sharpe_to_beat"] > honest["per_observation_sharpe_to_beat"]


def test_deflated_sharpe_refuses_tiny_samples():
    result = honesty.deflated_sharpe(0.1, 2, trials=1)
    assert result["deflated_sharpe_probability"] is None
    assert "too few observations" in result["note"]


def test_report_states_the_count_without_passing_judgement():
    """The number is reported; the reading is left to whoever ran the specs.

    An engine cannot tell six attempts at one hypothesis from six unrelated
    ideas, so it must not label either one a failure.
    """
    result = honesty.deflated_sharpe(
        0.01, 1000, trials=99, trial_sharpes=[0.01, 0.2, 0.4]
    )
    assert result["trials_considered"] == 99
    assert "verdict" not in result
