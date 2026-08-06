"""The data layer: fetch it, stamp it with two dates, hand it over.

Vintage has two halves and they answer different questions. This one answers
*what was known, and when* — sources, the registry that names their fields, the
HTTP and cache plumbing underneath, the envelope every value travels in, and
the point-in-time panel built on `known_at`. It has no opinion about strategies
and computes no performance statistic.

The other half is `vintage.engine`: costs, deflated Sharpe, the trial ledger.
It reads this layer. This layer must never read it, and `tests/test_layering.py`
fails the build if that arrow ever reverses.

The separation is not tidiness. A notebook reproducing a paper's GARCH fit or
its eigenvalue counts needs data and nothing else — dragging a backtester into
it means a parity break could come from either side, and you cannot tell which.

    from vintage.data import registry, sources
    from vintage.data import pit          # the known_at panel
"""

from __future__ import annotations

from .. import cache, envelope, http, pit, registry, sources  # noqa: F401

__all__ = ["cache", "envelope", "http", "pit", "registry", "sources"]
