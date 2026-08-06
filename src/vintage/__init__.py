"""Vintage — point-in-time financial data, as a library and as an MCP server.

    import vintage as v
    v.prices("AAPL")
    v.claim("Mom12m")

Every function is documented in `vintage.sdk`. The MCP server lives in
`vintage.server` and exposes the same data behind six verbs.
"""

__version__ = "0.4.0"

from .sdk import (  # noqa: F401
    backtest,
    claim,
    claims,
    crypto,
    factors,
    filings,
    frame,
    fundamentals,
    macro,
    panel,
    prices,
    resolve,
    restatements,
    returns,
    search,
    sentiment,
    short_volume,
    signals,
    sources,
    trials,
)

__all__ = [
    "prices", "panel", "returns", "crypto", "fundamentals", "restatements",
    "filings", "resolve", "factors", "macro", "claim", "claims", "short_volume",
    "sentiment", "search", "sources", "signals", "backtest", "trials", "frame",
    "__version__",
]
