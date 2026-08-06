"""Exercise all six verbs against live free sources."""

import asyncio
import json

from vintage.server import backtest, benchmark, discover, events, fetch, resolve, status

UNIVERSE = ["AAPL", "MSFT", "JNJ", "XOM", "PG", "KO", "WMT", "JPM", "CAT", "MRK"]


def show(title, raw, keys=None, chars=700):
    data = json.loads(raw)
    print(f"\n===== {title} =====")
    if not data.get("ok"):
        print("FAIL:", data.get("error"))
        return data
    trimmed = {k: v for k, v in data.items() if keys is None or k in keys}
    print(json.dumps(trimmed, indent=2, default=str)[:chars])
    return data


async def main():
    show("resolve AAPL", await resolve("AAPL"), ["entity", "ticker", "cik", "name", "exchange"])

    show("discover revenue @AAPL", await discover("revenue", entity="AAPL", limit=5), ["matches", "warnings"])

    show(
        "fetch us-gaap:Assets @AAPL as_of 2020-01-01",
        await fetch("us-gaap:Assets", entity="AAPL", form="10-K", as_of="2020-01-01"),
        ["row_count", "warnings", "restatements"],
    )

    show("fetch french:ff3", await fetch("french:ff3", limit=3), ["row_count", "sources", "rows"])

    show("fetch price:close @AAPL", await fetch("price:close", entity="AAPL", limit=2), ["row_count", "rows"])

    show("events AAPL", await events("AAPL", limit=6), ["form_counts", "row_count"])

    print("\n===== backtest momentum_12_1 =====")
    run = json.loads(await backtest(UNIVERSE, signal="momentum_12_1", start="2010-01-01"))
    if not run.get("ok"):
        print("FAIL:", run.get("error"))
        return
    print(json.dumps({"spec": run["spec"], "stats": run["stats"], "honesty": run["honesty"]}, indent=2))

    print("\n===== second spec (trial count should rise) =====")
    run2 = json.loads(await backtest(UNIVERSE, signal="reversal_1m", start="2010-01-01"))
    print(json.dumps(run2.get("honesty", {}), indent=2))

    show("benchmark run1 vs ff3", await benchmark(run["run_id"], "ff3"), ["result"], chars=1200)

    show("status", await status(), ["cache", "fred_key_configured", "specs_tried_this_session"])


asyncio.run(main())
