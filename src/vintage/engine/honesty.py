"""The part that makes a backtest engine trustworthy instead of dangerous.

A conversational backtester is an overfitting machine unless it counts how
many times you asked. This module keeps that count for the session and
deflates the Sharpe accordingly.

Deflated Sharpe follows Bailey & Lopez de Prado (2014). No scipy, the normal
CDF and its inverse are implemented directly.
"""

from __future__ import annotations

import math
from typing import Any

EULER = 0.5772156649015329

# Session-level trial log. This is deliberately global: the whole point is
# that trial 40 must know about trials 1-39.
_trials: list[dict[str, Any]] = []


def record_trial(spec: dict[str, Any], sharpe: float) -> int:
    _trials.append({"spec": spec, "sharpe": sharpe})
    return len(_trials)


def trial_count() -> int:
    return len(_trials)


def reset_trials() -> int:
    count = len(_trials)
    _trials.clear()
    return count


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Inverse normal CDF, Acklam's rational approximation."""
    if not 0.0 < p < 1.0:
        return math.inf if p >= 1.0 else -math.inf

    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00]

    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def expected_max_sharpe(trials: int, sharpe_variance: float) -> float:
    """Highest Sharpe you would expect from `trials` worthless strategies."""
    if trials < 2 or sharpe_variance <= 0:
        return 0.0
    sd = math.sqrt(sharpe_variance)
    return sd * (
        (1 - EULER) * norm_ppf(1 - 1.0 / trials)
        + EULER * norm_ppf(1 - 1.0 / (trials * math.e))
    )


def deflated_sharpe(
    sharpe: float,
    n_obs: int,
    *,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    trials: int | None = None,
    trial_sharpes: list[float] | None = None,
) -> dict[str, Any]:
    """Probability the strategy's true Sharpe exceeds zero, after accounting
    for how many strategies were tried to find it."""
    trials = trials if trials is not None else max(1, trial_count())
    sharpes = trial_sharpes if trial_sharpes is not None else [t["sharpe"] for t in _trials]

    if len(sharpes) >= 2:
        mean = sum(sharpes) / len(sharpes)
        variance = sum((s - mean) ** 2 for s in sharpes) / (len(sharpes) - 1)
    else:
        variance = 1.0 / max(1, n_obs - 1)

    threshold = expected_max_sharpe(trials, variance)

    denom = 1.0 - skew * sharpe + ((kurtosis - 1.0) / 4.0) * sharpe**2
    if denom <= 0 or n_obs < 3:
        return {
            "deflated_sharpe_probability": None,
            "note": "too few observations to deflate",
            "trials_considered": trials,
        }

    statistic = (sharpe - threshold) * math.sqrt(n_obs - 1) / math.sqrt(denom)
    probability = norm_cdf(statistic)

    return {
        "deflated_sharpe_probability": round(probability, 4),
        "per_observation_sharpe": round(sharpe, 5),
        "per_observation_sharpe_to_beat": round(threshold, 5),
        "trials_considered": trials,
        "verdict": _verdict(probability, trials),
        "note": (
            "Sharpe figures in this block are per observation, not annualized, "
            "that is the frequency the deflation is defined at."
        ),
    }


def _verdict(probability: float, trials: int) -> str:
    if probability >= 0.95:
        return "survives multiple-testing adjustment"
    if probability >= 0.90:
        return "marginal, would not survive a stricter trial count"
    if trials > 1:
        return (
            f"does not survive. After {trials} trials this session, a Sharpe this "
            "high is what noise produces."
        )
    return "not significant even before adjusting for multiple testing"
