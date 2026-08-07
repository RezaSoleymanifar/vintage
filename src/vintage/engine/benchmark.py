"""Score a return series against the published factors.

A factor you built is credible when it moves with the factor Ken French
publishes. This is the number that turns "I implemented momentum" into
"I implemented momentum and here is the correlation."
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _to_monthly(returns: pd.Series) -> pd.Series:
    return (1 + returns).resample("ME").prod() - 1


def compare(
    strategy: pd.Series,
    factors: pd.DataFrame,
    *,
    risk_free: pd.Series | None = None,
) -> dict[str, Any]:
    """Correlations against each factor, plus an OLS attribution.

    Returns alpha, betas, R-squared, and the single most correlated factor.
    Which is usually the honest answer to "what did I actually build?"

    Every coefficient carries a t-statistic, because a 0.4%/month alpha and a
    0.9%/month alpha look alike until you know which one the data can tell
    apart from zero.
    """
    monthly = _to_monthly(strategy).dropna()
    factors = factors.copy()
    factors.index = pd.to_datetime(factors.index)
    factors = factors.resample("ME").last()

    joined = pd.concat([monthly.rename("strategy"), factors], axis=1).dropna()
    if len(joined) < 12:
        return {
            "error": (
                f"Only {len(joined)} overlapping months with the factor series. "
                "Need at least 12 to say anything."
            )
        }

    y = joined["strategy"]
    if risk_free is not None and "RF" in joined:
        y = y - joined["RF"]

    exposures = [c for c in joined.columns if c not in ("strategy", "RF")]
    x = joined[exposures]

    correlations = {c: round(float(y.corr(x[c])), 4) for c in exposures}

    design = np.column_stack([np.ones(len(x)), x.values])
    coefficients, *_ = np.linalg.lstsq(design, y.values, rcond=None)
    fitted = design @ coefficients
    residual = y.values - fitted
    total_ss = float(((y.values - y.values.mean()) ** 2).sum())
    r_squared = 1 - float((residual**2).sum()) / total_ss if total_ss > 0 else 0.0

    best = max(correlations, key=lambda k: abs(correlations[k])) if correlations else None

    # Standard errors, so an alpha comes with the one number that says whether
    # to believe it. A point estimate alone makes 0.39%/mo and 0.90%/mo look
    # equally real when one is noise and the other is not.
    errors = _standard_errors(design, residual)
    t_stats = (
        [c / e if e > 0 else None for c, e in zip(coefficients, errors)]
        if errors is not None else [None] * len(coefficients)
    )

    return {
        "months_compared": len(joined),
        "correlations": correlations,
        "closest_published_factor": best,
        "closest_correlation": correlations.get(best) if best else None,
        "alpha_monthly": round(float(coefficients[0]), 5),
        "alpha_annualized": round(float((1 + coefficients[0]) ** 12 - 1), 4),
        "alpha_t_stat": _round(t_stats[0]),
        "alpha_standard_error": _round(errors[0] if errors is not None else None, 5),
        "betas": {
            name: round(float(value), 4)
            for name, value in zip(exposures, coefficients[1:])
        },
        "beta_t_stats": {
            name: _round(t)
            for name, t in zip(exposures, t_stats[1:])
        },
        "r_squared": round(r_squared, 4),
        "degrees_of_freedom": max(0, len(joined) - design.shape[1]),
        "reading": _reading(best, correlations.get(best) if best else None, r_squared),
        "significance_note": (
            "t is the estimate over its standard error. Above 2 is the "
            "conventional line; Harvey, Liu & Zhu (2016) argue 3 is the honest "
            "one for anything found by searching. t rises with the square root "
            "of the sample, so a long history flatters it."
        ),
    }


def _round(value: float | None, places: int = 3) -> float | None:
    return None if value is None else round(float(value), places)


def _standard_errors(design: np.ndarray, residual: np.ndarray) -> np.ndarray | None:
    """Classical OLS standard errors: sqrt of the diagonal of s^2 (X'X)^-1.

    Returns None when the design is rank deficient or there are no degrees of
    freedom left, rather than handing back an infinite t-statistic.
    """
    n, k = design.shape
    if n <= k:
        return None
    sigma_squared = float((residual**2).sum()) / (n - k)
    try:
        covariance = np.linalg.inv(design.T @ design) * sigma_squared
    except np.linalg.LinAlgError:
        return None
    diagonal = np.diag(covariance)
    if np.any(diagonal < 0):
        return None
    return np.sqrt(diagonal)


def _reading(best: str | None, correlation: float | None, r_squared: float) -> str:
    if best is None or correlation is None:
        return "No factor overlap to interpret."
    magnitude = abs(correlation)
    if magnitude >= 0.9:
        return f"This is {best}. You reproduced a published factor, which is the point."
    if magnitude >= 0.6:
        return f"Mostly {best}, with something else on top. Check whether the residual survives costs."
    if r_squared >= 0.5:
        return "No single factor dominates, but the published set explains most of it."
    return (
        "Weak overlap with published factors. Either genuinely novel, or the "
        "implementation differs from the paper. Verify the spec before believing it."
    )
