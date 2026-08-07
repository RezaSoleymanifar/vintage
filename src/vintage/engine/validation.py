"""The backtest-validation literature, implemented rather than cited.

Five things live here, each of which the README used to list as planned:

  purged_kfold                Lopez de Prado, AFML ch. 7
  combinatorial_purged        Lopez de Prado, AFML ch. 12
  probability_of_overfitting  Bailey, Borwein, Lopez de Prado & Zhu (2017)
  min_backtest_length         Bailey, Borwein, Lopez de Prado & Zhu (2014)
  newey_west_t                Newey & West (1987)

The common thread is that a single in-sample number is not evidence. Splitting
a financial series naively does not fix that either, because a label computed
over the next `horizon` days leaks across any boundary you draw. Purging and
embargoing are what make the split mean what it looks like it means.

No scipy. The normal CDF and its inverse come from `honesty`.
"""

from __future__ import annotations

import itertools
import math
from typing import Any, Iterable, Sequence

from .honesty import expected_max_sharpe, norm_ppf

Split = tuple[list[int], list[int]]


# ------------------------------------------------------------------ splitting

def _contiguous_groups(n_obs: int, n_groups: int) -> list[list[int]]:
    """Split 0..n_obs into contiguous groups, the extra rows going to the front."""
    if n_groups < 2:
        raise ValueError("A split needs at least 2 groups")
    if n_obs < n_groups:
        raise ValueError(f"{n_obs} observations cannot fill {n_groups} groups")
    base, extra = divmod(n_obs, n_groups)
    groups, start = [], 0
    for i in range(n_groups):
        size = base + (1 if i < extra else 0)
        groups.append(list(range(start, start + size)))
        start += size
    return groups


def _train_for(test: Sequence[int], n_obs: int, horizon: int, embargo: int) -> list[int]:
    """Every index that can be trained on without touching the test window.

    Two exclusions, and they are different. **Purging** drops a training row
    whose own label window reaches into the test block: a row at i is labelled
    by what happens through i + horizon, so if that reaches the first test row
    it has seen the answer. **Embargo** drops rows just after the test block,
    because serial correlation makes them near-copies of the last test rows
    even though their label windows never overlap.
    """
    t0, t1 = test[0], test[-1]
    return [
        i for i in range(n_obs)
        if (i + horizon < t0) or (i > t1 + embargo)
    ]


def purged_kfold(
    n_obs: int,
    *,
    n_splits: int = 5,
    horizon: int = 1,
    embargo_pct: float = 0.01,
) -> list[Split]:
    """k contiguous test folds, each with its training set purged and embargoed.

    Returns [(train_index, test_index), ...] as plain integer positions, so it
    works on a numpy array, a pandas frame, or a list, and pulls in nothing.
    """
    if horizon < 0:
        raise ValueError("horizon cannot be negative")
    embargo = int(round(n_obs * max(embargo_pct, 0.0)))
    return [
        (_train_for(test, n_obs, horizon, embargo), list(test))
        for test in _contiguous_groups(n_obs, n_splits)
    ]


def combinatorial_purged(
    n_obs: int,
    *,
    n_groups: int = 6,
    n_test_groups: int = 2,
    horizon: int = 1,
    embargo_pct: float = 0.01,
) -> list[Split]:
    """Every way of holding out `n_test_groups` of `n_groups` blocks at once.

    Purged k-fold gives one path through history and one number. This gives
    C(n_groups, n_test_groups) of them, which is a distribution: the spread
    across paths is the part that tells you whether the single number was luck.

    The test blocks in one split need not be adjacent, so purging is applied
    per block rather than once around the pair.
    """
    if not 1 <= n_test_groups < n_groups:
        raise ValueError("n_test_groups must be at least 1 and fewer than n_groups")
    groups = _contiguous_groups(n_obs, n_groups)
    embargo = int(round(n_obs * max(embargo_pct, 0.0)))

    splits: list[Split] = []
    for chosen in itertools.combinations(range(n_groups), n_test_groups):
        test = sorted(i for g in chosen for i in groups[g])
        train = set(range(n_obs))
        for g in chosen:
            train &= set(_train_for(groups[g], n_obs, horizon, embargo))
        splits.append((sorted(train), test))
    return splits


# ------------------------------------------------ probability of overfitting

def _sharpe(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean / math.sqrt(var) if var > 0 else 0.0


def probability_of_overfitting(
    matrix: Sequence[Sequence[float]],
    *,
    n_blocks: int = 8,
) -> dict[str, Any]:
    """PBO by combinatorially symmetric cross-validation.

    `matrix` is observations x configurations: one column per thing you tried,
    one row per period, all columns covering the same periods.

    Split the rows into `n_blocks` blocks. For every way of choosing half the
    blocks as in-sample, pick the column that won in sample and see where it
    ranked out of sample. If winning in sample said nothing, that rank is
    uniform and the winner lands below the out-of-sample median half the time.
    PBO is how often that happens, and anything near or above 0.5 means the
    selection procedure is fitting noise.
    """
    n_obs = len(matrix)
    n_cfg = len(matrix[0]) if n_obs else 0
    if n_cfg < 2:
        return {"pbo": None, "note": "needs at least two configurations to compare"}
    if n_blocks % 2:
        n_blocks -= 1
    if n_obs < n_blocks * 2 or n_blocks < 2:
        return {"pbo": None, "note": f"needs at least {max(n_blocks, 2) * 2} observations"}

    blocks = _contiguous_groups(n_obs, n_blocks)
    half = n_blocks // 2

    logits: list[float] = []
    below = 0
    for chosen in itertools.combinations(range(n_blocks), half):
        train_rows = [i for b in chosen for i in blocks[b]]
        test_rows = [i for b in range(n_blocks) if b not in chosen for i in blocks[b]]

        in_sample = [_sharpe([matrix[i][c] for i in train_rows]) for c in range(n_cfg)]
        out_sample = [_sharpe([matrix[i][c] for i in test_rows]) for c in range(n_cfg)]

        best = max(range(n_cfg), key=lambda c: in_sample[c])
        # Rank of the in-sample winner among out-of-sample results, 1 = worst.
        rank = 1 + sum(1 for c in range(n_cfg) if out_sample[c] < out_sample[best])
        omega = rank / (n_cfg + 1)
        omega = min(max(omega, 1e-9), 1 - 1e-9)
        logit = math.log(omega / (1 - omega))
        logits.append(logit)
        if logit <= 0:
            below += 1

    pbo = below / len(logits)
    return {
        "pbo": round(pbo, 4),
        "combinations": len(logits),
        "configurations": n_cfg,
        "median_logit": round(sorted(logits)[len(logits) // 2], 4),
        "verdict": (
            "selection is fitting noise" if pbo >= 0.5 else
            "selection carries some signal" if pbo >= 0.25 else
            "in-sample ranking held up out of sample"
        ),
        "note": (
            "PBO is the share of splits where the in-sample winner ranked below "
            "the out-of-sample median. 0.5 is what pure noise produces."
        ),
    }


# --------------------------------------------------- minimum backtest length

def min_backtest_length(
    trials: int,
    annual_sharpe: float,
    *,
    observations_per_year: int = 252,
) -> dict[str, Any]:
    """Years of history needed before a Sharpe this high means anything.

    With N strategies tried and a true Sharpe of zero, the best of them still
    posts an expected maximum Sharpe that grows with N. To claim the observed
    Sharpe beat that bar rather than met it, the sample has to be long enough,
    and the bar rises with the number of trials while the evidence only rises
    with time. This is the inequality solved for time.
    """
    if trials < 2:
        return {"min_backtest_years": None,
                "note": "with fewer than two trials there is no selection bias to correct"}
    if annual_sharpe <= 0:
        return {"min_backtest_years": None,
                "note": "a non-positive Sharpe needs no length to disbelieve"}

    years = 2.0 * math.log(trials) / (annual_sharpe ** 2)

    # A Sharpe near zero sends this to millions of years, which is arithmetically
    # right and useless to print. Past a century there is no such history to
    # have, and saying that is more informative than the number.
    beyond_available = years > 100.0

    return {
        "min_backtest_years": round(years, 2),
        "beyond_any_available_history": beyond_available,
        "trials_considered": trials,
        "observed_annual_sharpe": round(annual_sharpe, 3),
        "expected_max_sharpe_from_noise": round(
            expected_max_sharpe(trials, 1.0 / max(observations_per_year - 1, 1))
            * math.sqrt(observations_per_year), 3
        ),
        "note": (
            "Bailey, Borwein, Lopez de Prado & Zhu (2014). Below this many "
            "years, a Sharpe this high is expected from noise alone once the "
            "trial count is accounted for."
            + (" No sample this long exists, so this Sharpe cannot be "
               "distinguished from noise at this trial count." if beyond_available else "")
        ),
    }


# ------------------------------------------------------- autocorrelation-safe

def newey_west_t(returns: Sequence[float], *, lags: int | None = None) -> dict[str, Any]:
    """t-statistic of the mean return, with a HAC standard error.

    Daily strategy returns are autocorrelated, and the ordinary standard error
    assumes they are not. It is therefore too small, and the t-statistic built
    on it is too large. Newey & West widen it by the weighted sum of the first
    `lags` autocovariances, with Bartlett weights so the estimate stays
    positive.
    """
    n = len(returns)
    if n < 8:
        return {"newey_west_t": None, "note": "too few observations for a HAC estimate"}

    if lags is None:
        lags = int(math.floor(4 * (n / 100.0) ** (2.0 / 9.0)))
    lags = max(0, min(lags, n - 2))

    mean = sum(returns) / n
    dev = [r - mean for r in returns]

    gamma0 = sum(d * d for d in dev) / n
    if gamma0 <= 0:
        return {"newey_west_t": None, "note": "returns have no variation"}

    total = gamma0
    for lag in range(1, lags + 1):
        weight = 1.0 - lag / (lags + 1.0)
        cov = sum(dev[i] * dev[i - lag] for i in range(lag, n)) / n
        total += 2.0 * weight * cov

    if total <= 0:
        return {"newey_west_t": None, "note": "HAC variance estimate was not positive"}

    se = math.sqrt(total / n)
    t_stat = mean / se if se > 0 else 0.0
    plain = mean / math.sqrt(gamma0 / n)

    return {
        "newey_west_t": round(t_stat, 3),
        "unadjusted_t": round(plain, 3),
        "lags": lags,
        "inflation_removed": round(plain - t_stat, 3),
        "note": (
            "Newey & West (1987) with Bartlett weights. The unadjusted figure "
            "assumes independent returns, which daily strategy returns are not."
        ),
    }


# --------------------------------------------------------------- trade impact

def sqrt_impact_bps(
    participation: float,
    *,
    daily_volatility: float,
    coefficient: float = 1.0,
) -> float:
    """Market impact in basis points, growing with the root of participation.

    Almgren, Thum, Hauptmann & Li (2005): the temporary impact of a trade rises
    roughly with the square root of the fraction of daily volume it represents,
    scaled by the name's own volatility. A flat basis-point charge says a trade
    ten times larger costs ten times more; this says it costs about three times
    more per unit, which is the part that decides whether a strategy survives at
    size.
    """
    if participation <= 0 or daily_volatility <= 0:
        return 0.0
    return 10_000.0 * coefficient * daily_volatility * math.sqrt(participation)


def impact_report(
    turnover_per_rebalance: float,
    *,
    rebalances_per_year: float,
    notional: float | None,
    average_daily_volume: float | None,
    daily_volatility: float,
    coefficient: float = 1.0,
) -> dict[str, Any]:
    """What the square-root model charges this strategy, if size is known.

    Without a notional and a volume to compare it against, participation is
    undefined and this says so rather than inventing a number.
    """
    if not notional or not average_daily_volume:
        return {
            "square_root_impact": None,
            "note": (
                "Pass notional and average_daily_volume to price impact. Without "
                "them participation is unknown, and the flat cost_bps charge is "
                "all that has been applied."
            ),
        }
    participation = (turnover_per_rebalance * notional) / average_daily_volume
    per_rebalance = sqrt_impact_bps(
        participation, daily_volatility=daily_volatility, coefficient=coefficient
    )
    return {
        "square_root_impact": {
            "participation_of_daily_volume": round(participation, 5),
            "impact_bps_per_rebalance": round(per_rebalance, 2),
            "annual_drag": round(
                per_rebalance / 10_000.0 * rebalances_per_year, 5
            ),
        },
        "note": (
            "Almgren et al. (2005). Impact rises with the square root of "
            "participation, so this grows sublinearly with size rather than "
            "staying flat like the basis-point charge."
        ),
    }


def align(series: Iterable[dict[str, float]]) -> tuple[list[str], list[list[float]]]:
    """Several date->return maps into one matrix over the dates they share.

    PBO compares configurations over identical periods; a column covering a
    different window would be scored against a different market rather than a
    different idea.
    """
    series = list(series)
    if not series:
        return [], []
    common = set(series[0])
    for s in series[1:]:
        common &= set(s)
    dates = sorted(common)
    return dates, [[s[d] for s in series] for d in dates]
