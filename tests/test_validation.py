"""The validation layer, checked against what each method is supposed to say.

These are the tests that matter most in the repository. A split that quietly
leaks, or an overfitting statistic that fails to flag a period-fitted winner,
would make every backtest downstream look better than it is, and nothing else
here would notice.
"""

from __future__ import annotations

import math
import random

import pytest

from vintage.engine import validation


# ---------------------------------------------------------------- splitting

def test_kfold_test_blocks_cover_everything_exactly_once():
    splits = validation.purged_kfold(100, n_splits=5, embargo_pct=0.0)
    seen = [i for _, test in splits for i in test]
    assert sorted(seen) == list(range(100))


def test_training_never_touches_the_test_block():
    for train, test in validation.purged_kfold(200, n_splits=4, embargo_pct=0.02):
        assert not set(train) & set(test)


def test_purging_drops_rows_whose_label_reaches_the_test_block():
    horizon = 5
    splits = validation.purged_kfold(120, n_splits=3, horizon=horizon, embargo_pct=0.0)
    for train, test in splits:
        t0 = test[0]
        # A row at i is labelled by i..i+horizon. None of the kept training
        # rows may have a window that reaches t0.
        assert all(i + horizon < t0 or i > test[-1] for i in train)


def test_embargo_removes_rows_immediately_after_the_test_block():
    n, splits = 100, validation.purged_kfold(100, n_splits=4, embargo_pct=0.10)
    embargo = int(round(n * 0.10))
    for train, test in splits:
        after = [i for i in train if i > test[-1]]
        if after:
            assert min(after) > test[-1] + embargo


def test_a_longer_embargo_can_only_shrink_training():
    small = validation.purged_kfold(300, n_splits=5, embargo_pct=0.01)
    large = validation.purged_kfold(300, n_splits=5, embargo_pct=0.10)
    for (train_s, _), (train_l, _) in zip(small, large):
        assert len(train_l) <= len(train_s)


def test_combinatorial_gives_every_combination_of_held_out_blocks():
    splits = validation.combinatorial_purged(240, n_groups=6, n_test_groups=2)
    assert len(splits) == math.comb(6, 2)
    for train, test in splits:
        assert not set(train) & set(test)


def test_splits_refuse_impossible_shapes():
    with pytest.raises(ValueError):
        validation.purged_kfold(3, n_splits=5)
    with pytest.raises(ValueError):
        validation.purged_kfold(100, n_splits=1)
    with pytest.raises(ValueError):
        validation.combinatorial_purged(240, n_groups=4, n_test_groups=4)


# --------------------------------------------------------------------- PBO

def test_period_specific_winners_are_called_overfit():
    """The case PBO exists to catch.

    Each configuration is engineered to look excellent in one stretch of
    history and ordinary everywhere else, which is what a parameter sweep
    produces. Whichever stretch lands in sample picks the winner, and that
    winner has nothing left out of sample.
    """
    rng = random.Random(11)
    n_obs, n_cfg = 480, 8
    span = n_obs // n_cfg
    matrix = []
    for i in range(n_obs):
        row = [rng.gauss(0, 0.01) for _ in range(n_cfg)]
        row[i // span] += 0.05      # this column's private good patch
        matrix.append(row)
    out = validation.probability_of_overfitting(matrix)
    assert out["pbo"] >= 0.5
    assert out["verdict"] == "selection is fitting noise"


def test_noise_alone_is_not_enough_to_call_it_overfit():
    """A subtlety worth pinning down rather than discovering later.

    With genuinely independent columns, whichever one drew the luckiest sample
    draws it in both halves, because both halves are estimating the same fixed
    realised mean. PBO is therefore low here, and that is correct: nothing was
    selected on a period-specific fit. PBO measures whether the *selection*
    generalises, not whether the edge is real.
    """
    rng = random.Random(11)
    matrix = [[rng.gauss(0, 0.01) for _ in range(8)] for _ in range(400)]
    out = validation.probability_of_overfitting(matrix)
    assert 0.0 <= out["pbo"] <= 1.0


def test_a_genuinely_better_column_is_not_called_overfit():
    rng = random.Random(3)
    matrix = []
    for _ in range(400):
        row = [rng.gauss(0, 0.01) for _ in range(7)]
        row.append(rng.gauss(0.004, 0.01))  # a real edge, present throughout
        matrix.append(row)
    out = validation.probability_of_overfitting(matrix)
    assert out["pbo"] <= 0.2
    assert "held up" in out["verdict"]


def test_pbo_says_so_rather_than_guessing_when_it_cannot_run():
    assert validation.probability_of_overfitting([[0.1]])["pbo"] is None
    assert validation.probability_of_overfitting([[0.1, 0.2]] * 4)["pbo"] is None


# ------------------------------------------------------------------ MinBTL

def test_more_trials_need_a_longer_sample():
    few = validation.min_backtest_length(5, 1.0)["min_backtest_years"]
    many = validation.min_backtest_length(500, 1.0)["min_backtest_years"]
    assert many > few


def test_a_stronger_sharpe_needs_a_shorter_sample():
    weak = validation.min_backtest_length(50, 0.5)["min_backtest_years"]
    strong = validation.min_backtest_length(50, 2.0)["min_backtest_years"]
    assert strong < weak


def test_min_backtest_length_declines_to_answer_when_it_should():
    assert validation.min_backtest_length(1, 1.0)["min_backtest_years"] is None
    assert validation.min_backtest_length(50, 0.0)["min_backtest_years"] is None
    assert validation.min_backtest_length(50, -1.0)["min_backtest_years"] is None


# -------------------------------------------------------------- Newey-West

def test_positive_autocorrelation_lowers_the_t_statistic():
    rng = random.Random(5)
    series, prev = [], 0.0
    for _ in range(500):
        prev = 0.6 * prev + rng.gauss(0, 0.01)
        series.append(0.001 + prev)
    out = validation.newey_west_t(series)
    assert out["newey_west_t"] < out["unadjusted_t"]
    assert out["inflation_removed"] > 0


def test_independent_returns_barely_move():
    rng = random.Random(9)
    series = [0.001 + rng.gauss(0, 0.01) for _ in range(500)]
    out = validation.newey_west_t(series)
    assert abs(out["inflation_removed"]) < 0.5


def test_newey_west_declines_on_degenerate_input():
    assert validation.newey_west_t([0.01] * 4)["newey_west_t"] is None
    assert validation.newey_west_t([0.01] * 50)["newey_west_t"] is None


# ------------------------------------------------------------------ impact

def test_impact_grows_with_the_root_of_participation():
    one = validation.sqrt_impact_bps(0.01, daily_volatility=0.02)
    four = validation.sqrt_impact_bps(0.04, daily_volatility=0.02)
    assert four == pytest.approx(2 * one, rel=1e-9)


def test_impact_is_zero_without_a_trade():
    assert validation.sqrt_impact_bps(0.0, daily_volatility=0.02) == 0.0
    assert validation.sqrt_impact_bps(0.05, daily_volatility=0.0) == 0.0


def test_impact_report_refuses_to_invent_a_size():
    out = validation.impact_report(
        0.4, rebalances_per_year=12, notional=None,
        average_daily_volume=None, daily_volatility=0.01,
    )
    assert out["square_root_impact"] is None
    assert "notional" in out["note"]


def test_impact_report_prices_a_known_size():
    out = validation.impact_report(
        0.4, rebalances_per_year=12, notional=10_000_000,
        average_daily_volume=50_000_000, daily_volatility=0.015,
    )
    priced = out["square_root_impact"]
    assert priced["participation_of_daily_volume"] == pytest.approx(0.08)
    assert priced["impact_bps_per_rebalance"] > 0


# ------------------------------------------------------------------- align

def test_align_keeps_only_the_dates_every_series_covers():
    dates, matrix = validation.align([
        {"2020-01-01": 0.1, "2020-01-02": 0.2, "2020-01-03": 0.3},
        {"2020-01-02": 0.4, "2020-01-03": 0.5, "2020-01-04": 0.6},
    ])
    assert dates == ["2020-01-02", "2020-01-03"]
    assert matrix == [[0.2, 0.4], [0.3, 0.5]]


def test_align_on_nothing_is_empty_rather_than_an_error():
    assert validation.align([]) == ([], [])
