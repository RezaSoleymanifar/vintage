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

    return {
        "months_compared": len(joined),
        "correlations": correlations,
        "closest_published_factor": best,
        "closest_correlation": correlations.get(best) if best else None,
        "alpha_monthly": round(float(coefficients[0]), 5),
        "alpha_annualized": round(float((1 + coefficients[0]) ** 12 - 1), 4),
        "betas": {
            name: round(float(value), 4)
            for name, value in zip(exposures, coefficients[1:])
        },
        "r_squared": round(r_squared, 4),
        "reading": _reading(best, correlations.get(best) if best else None, r_squared),
    }


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
