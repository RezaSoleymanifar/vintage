"""Vintage, point-in-time financial data, as a library and as an MCP server.

    import vintage as v
    v.prices("AAPL")
    v.claim("Mom12m")

Every function is documented in `vintage.sdk`. The MCP server lives in
`vintage.server` and exposes the same data behind six verbs.
"""

__version__ = "0.9.0"

from .sdk import (  # noqa: F401
    backtest,
    claim,
    claims,
    cross_section,
    corporate_actions,
    crypto,
    delistings,
    factors,
    fx,
    filings,
    frame,
    index,
    fundamentals,
    macro,
    panel,
    positioning,
    prices,
    resolve,
    survivorship_warning,
    restatements,
    returns,
    search,
    sentiment,
    short_volume,
    signals,
    sources,
    volatility,
    treasury_yields,
    trials,
)

__all__ = [
    "prices", "panel", "returns", "crypto", "corporate_actions", "fundamentals", "restatements",
    "filings", "resolve", "factors", "macro", "claim", "claims", "short_volume",
    "sentiment", "search", "sources", "signals", "backtest", "trials", "frame",
    "delistings", "survivorship_warning", "fx", "volatility", "index",
    "cross_section", "treasury_yields", "positioning",
    "__version__",
]
