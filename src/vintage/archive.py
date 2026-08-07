"""The recorder: keep what the source will not keep.

Most of Vintage reads. This writes. The distinction matters because a handful of
sources publish only the present: ask them tomorrow and yesterday is gone, and no
amount of money buys it back. EDGAR states a filer's *current* industry code with
no date of change. ApeWisdom publishes the board as it stands. Ken French rebuilds
the factor files on each release. Yahoo re-adjusts every historical close the
morning after a split.

Recording those turns a read-only federation into an asset. Not a licensed one, a
created one: the history exists because something was running, which is why it
cannot be bought, scraped late, or competed away by anyone starting today.

The shape is the one `envelope.row` already uses, bitemporal and append-only:

    observed_at   the period the value describes
    known_at      when it became public, or when we read it
    recorded_at   when this process wrote it down

Two rules make it small and safe:

  append only     a file, once a day closes, is never rewritten. That makes every
                  partition immutable, infinitely cacheable, and safe to serve.
  change only     a value identical to the last one recorded for the same
                  (entity, field, observed_at) is not written again. Mentions move
                  hourly and cost their full size; an industry code moves once a
                  decade and costs almost nothing.

Storage is gzipped JSONL partitioned by the date we recorded it, which keeps the
write path append-only and needs no database.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

DEFAULT_ROOT = os.environ.get(
    "VINTAGE_ARCHIVE_DIR",
    os.path.join(os.path.expanduser("~"), ".vintage-archive"),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _partition(cadence: str) -> str:
    """The filename a write lands in. Hourly targets get an hourly file so each
    commit adds a small final file rather than replacing a growing one; git
    stores a whole new blob every time a file changes, which turned 25 MB of
    real data into an estimated 365 MB of repository."""
    now = datetime.now(timezone.utc)
    if cadence == "hourly":
        return now.strftime("%Y-%m-%dT%H")
    return now.date().isoformat()


def _today() -> str:
    """The UTC date, so a partition's name and the stamps inside it agree. Local
    dates disagree with UTC for part of every day, which put rows stamped the 7th
    into a file called the 6th and made an `as_of` on that day return nothing."""
    return datetime.now(timezone.utc).date().isoformat()


def _key(row: dict[str, Any]) -> str:
    """What makes two observations the same fact rather than a new one."""
    return "|".join(str(row.get(k, "")) for k in ("entity", "field", "observed_at"))


def _digest(value: Any) -> str:
    return hashlib.sha1(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]


class Archive:
    """An append-only bitemporal store on the local filesystem.

    `root/<slug>/<YYYY-MM-DD>.jsonl.gz` holds everything recorded for one target
    on one day. `root/<slug>/state.json` holds the last value seen per key, which
    is what makes change-only writing possible without reading the history back.
    """

    def __init__(self, root: str = DEFAULT_ROOT) -> None:
        self.root = root

    def _dir(self, slug: str) -> str:
        path = os.path.join(self.root, slug)
        os.makedirs(path, exist_ok=True)
        return path

    def _state_path(self, slug: str) -> str:
        return os.path.join(self._dir(slug), "state.json")

    def load_state(self, slug: str) -> dict[str, str]:
        try:
            with open(self._state_path(slug), encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def save_state(self, slug: str, state: dict[str, str]) -> None:
        # Written whole and replaced, so an interrupted run cannot leave a state
        # file that claims to have recorded something it did not.
        tmp = self._state_path(slug) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, sort_keys=True)
        os.replace(tmp, self._state_path(slug))

    def append(self, slug: str, rows: Iterable[dict[str, Any]],
               cadence: str = "daily") -> int:
        """Write rows whose value differs from the last one recorded. Returns the
        number actually written, which is the number that matters: a run that
        writes nothing is a run where nothing changed, not a failed one."""
        state = self.load_state(slug)
        stamp = _now()
        partition = os.path.join(self._dir(slug), f"{_partition(cadence)}.jsonl.gz")

        fresh = []
        for row in rows:
            key, digest = _key(row), _digest(row.get("value"))
            if state.get(key) == digest:
                continue
            state[key] = digest
            row = {**row, "recorded_at": stamp}
            # A source that cannot say when a value became public gets its
            # known_at from us, stamped at the moment we saw it. That is the
            # whole trade: the row is not point-in-time back to its origin, but
            # it is point-in-time from the day recording started, and nobody who
            # starts later can reconstruct it.
            if not row.get("known_at"):
                row["known_at"] = stamp
                row["vintage"] = "recorded-at-read"
            fresh.append(row)

        if fresh:
            # Appending to a gzip member is legal: concatenated members decode as
            # one stream, so a day's file grows without ever being rewritten.
            with gzip.open(partition, "at", encoding="utf-8") as fh:
                for row in fresh:
                    fh.write(json.dumps(row, default=str) + "\n")
            self.save_state(slug, state)
        return len(fresh)

    def read(self, slug: str, as_of: str | None = None) -> list[dict[str, Any]]:
        """Every row recorded for a target, optionally as the world knew it."""
        out: list[dict[str, Any]] = []
        folder = self._dir(slug)
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".jsonl.gz"):
                continue
            with gzip.open(os.path.join(folder, name), "rt", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    if as_of and str(row.get("known_at") or row.get("recorded_at", ""))[:10] > as_of:
                        continue
                    out.append(row)
        return out

    def stats(self, slug: str) -> dict[str, Any]:
        folder = self._dir(slug)
        files = [f for f in os.listdir(folder) if f.endswith(".jsonl.gz")]
        size = sum(os.path.getsize(os.path.join(folder, f)) for f in files)
        return {
            "target": slug,
            "partitions": len(files),
            "bytes": size,
            "first_day": min(files)[:10] if files else None,
            "last_day": max(files)[:10] if files else None,
            "newest_partition": max(files)[:-9] if files else None,
            "keys_tracked": len(self.load_state(slug)),
        }


# --------------------------------------------------------------------- targets
# What is worth recording, and why. A source belongs here only if asking it
# tomorrow loses something: if it keeps its own history, recording it is storage
# spent on a copy. `tools/moat_study.py` derives this list from the registry and
# fails if the two disagree.
#   (slug, cadence, what it costs to lose, how to fetch it)
# `COVERS` maps each slug to the registry source it records, so the study can
# check coverage by identity instead of guessing from substrings.
COVERS = {
    "sector-sic": "sec-edgar-sic",
    "ape-boards": "apewisdom",
    "french-ff3": "ken-french-data-library",
    "price-as-printed": "yahoo-finance",
    "frames-cross-section": "sec-xbrl-frames",
    "crypto-listings": "coinbase-exchange",
}
Target = tuple[str, str, str, Callable[[], Any]]

# Whose industry code we watch. Start with the names a cross-sectional test
# actually runs on; the list is the cheap part to grow, the history is not.
SIC_WATCHLIST = ["AAPL", "MSFT", "JNJ", "XOM", "JPM", "KO", "PG", "WMT",
                 "CVX", "MRK", "HD", "INTC", "CSCO", "VZ", "BA", "MMM",
                 "CAT", "IBM", "NKE", "MCD", "AMZN", "GOOGL", "META", "TSLA",
                 "NVDA", "AMD", "PFE", "T", "DIS", "GS"]


def targets() -> list[Target]:
    import vintage as v

    return [
        ("sector-sic", "weekly",
         "EDGAR states a filer's current industry code with no date of change. "
         "Point-in-time industry labels are otherwise licensed, and every "
         "cross-sectional neutraliser needs one.",
         lambda: _rows(v.sectors(SIC_WATCHLIST))),
        ("ape-boards", "hourly",
         "ApeWisdom publishes the present board only. There is no history "
         "endpoint and no way to buy last Tuesday.",
         lambda: _rows(v.sentiment("all-stocks"))),
        ("french-ff3", "monthly",
         "The factor files are rebuilt on each release, so a number can change "
         "with no record that it did.",
         lambda: _rows(v.factors("ff3").tail(6))),
        ("price-as-printed", "daily",
         "Yahoo re-adjusts every historical close the morning after a split or "
         "dividend, so today's history is not what anyone traded on. Recording "
         "the close as printed keeps the unadjusted series.",
         lambda: _rows(v.prices("AAPL", field="close").tail(3))),
        ("frames-cross-section", "daily",
         "A frame is every filer on one concept but carries no filing date. "
         "Snapshotting it dates the cross-section, which is what a sort needs "
         "and what the endpoint refuses to give.",
         lambda: _rows(v.cross_section("Assets", "CY2025Q4I").head(400))),
        ("crypto-listings", "daily",
         "Coinbase lists currently-traded products only. Recording the list is "
         "the only way to know what was tradable then, which is crypto "
         "survivorship.",
         lambda: _rows(v.crypto("BTC-USD").tail(2))),
    ]


def _rows(frame) -> list[dict[str, Any]]:
    """A pandas frame to envelope-shaped dicts, keeping both dates."""
    if frame is None or len(frame) == 0:
        return []
    records = frame.reset_index().to_dict("records")
    out = []
    for r in records:
        row = {str(k): v for k, v in r.items()}
        row.setdefault("observed_at", str(row.get("index", ""))[:10])
        row.pop("index", None)
        out.append(row)
    return out
