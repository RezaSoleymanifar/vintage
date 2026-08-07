"""Run the recorder. This is the thing that has to keep running.

Every other tool here can be re-run tomorrow and produce the same answer. This
one cannot: a target that is not polled today loses today, permanently, and no
amount of catching up later fills it in. That asymmetry is the whole reason the
archive is worth anything, and it is also why this script is written to fail
loudly and partially rather than quietly and completely.

    uv run python tools/record.py                 # every target due now
    uv run python tools/record.py --cadence hourly
    uv run python tools/record.py --stats

A target that fails does not stop the others. The exit code is non-zero if any
failed, so a scheduler surfaces it, but everything reachable is still written.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

os.environ.setdefault("VINTAGE_USER_AGENT", "Vintage archive reza@soleymanifar.com")

from vintage.archive import Archive, targets  # noqa: E402

# Which cadences are due when. A weekly target polled hourly wastes requests
# against a rate limit that matters; polled monthly it misses changes.
DUE = {
    "hourly": {"hourly"},
    "daily": {"hourly", "daily"},
    "weekly": {"hourly", "daily", "weekly"},
    "monthly": {"hourly", "daily", "weekly", "monthly"},
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cadence", default="monthly", choices=sorted(DUE),
                    help="run everything due at this cadence or more often")
    ap.add_argument("--stats", action="store_true", help="report what is held, write nothing")
    args = ap.parse_args()

    archive = Archive()
    if args.stats:
        total = 0
        for slug, cadence, _why, _fetch in targets():
            st = archive.stats(slug)
            total += st["bytes"]
            print(f"{slug:22} {cadence:8} {st['partitions']:4} days  "
                  f"{st['keys_tracked']:6} keys  {st['bytes'] / 1024:8.1f} KB  "
                  f"{st['first_day'] or '-'} .. {st['last_day'] or '-'}")
        print(f"{'total':22} {'':8} {'':4}       {'':6}       {total / 1024:8.1f} KB")
        return 0

    due = DUE[args.cadence]
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"recording at {stamp}, cadence <= {args.cadence}")

    failures = 0
    for slug, cadence, _why, fetch in targets():
        if cadence not in due:
            continue
        try:
            written = archive.append(slug, fetch(), cadence)
            print(f"  {slug:22} {written:5} new rows")
        except Exception as exc:                  # noqa: BLE001 - one target must not stop the rest
            failures += 1
            print(f"  {slug:22} FAILED {type(exc).__name__}: {str(exc)[:80]}", file=sys.stderr)

    if failures:
        print(f"{failures} target(s) failed; the rest were recorded", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
