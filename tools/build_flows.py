"""Ape Tape: where two independent groups of money actually moved.

One page, one claim, two clocks. The institutional half comes from Form 13F and
changes four times a year; the congressional half comes from STOCK Act periodic
transaction reports and changes continuously. A page that redraws both on the
same schedule would imply the 13F table moved when it did not, so each panel
carries its own as-of date and its own next-change date.

Everything here is computed from the sources at build time. There are no typed
numbers in the template, because a billboard whose figures were keyed in by hand
is exactly the artifact this project exists to argue against.

    python tools/build_flows.py        ->  docs/flows.html
"""

from __future__ import annotations

import asyncio
import datetime as dt
import html
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from vintage.http import SourceError                      # noqa: E402
from vintage.sources import congress, thirteenf           # noqa: E402

# The two quarters compared. A year apart, so the table shows a position
# changing rather than a quarter of noise.
NOW_Q, THEN_Q = "2026-03-31", "2025-03-31"

# 13F is due 45 days after quarter end. These are the dates the institutional
# half of this page can possibly change, and nothing between them will move it.
FILING_DUE = {
    "2026-03-31": dt.date(2026, 5, 15),
    "2026-06-30": dt.date(2026, 8, 14),
    "2026-09-30": dt.date(2026, 11, 14),
    "2026-12-31": dt.date(2027, 2, 17),
}

CONGRESS_YEAR = 2026


# ----------------------------------------------------------------- the data

async def _positions(manager: str, quarter: str):
    try:
        payload = await thirteenf.holdings(manager, field="value", quarter=quarter)
    except Exception:                                      # noqa: BLE001
        return None
    rows = payload["rows"] if isinstance(payload, dict) else payload
    out = {}
    for r in rows:
        cusip, shares = r.get("cusip"), r.get("shares")
        value = r.get("market_value_usd") or r.get("value")
        if not cusip or not shares or not value or r.get("put_call"):
            continue
        out[cusip] = (float(shares), float(value), r.get("issuer") or cusip)
    return out


async def institutional():
    """Net dollars traded per issuer, valued at the later quarter's price.

    Share counts are differenced, never dollar values: a position that only
    appreciated was not bought, and netting values across managers would draw a
    map of last year's returns instead of this year's trades.
    """
    flow: dict[str, float] = defaultdict(float)
    names: dict[str, str] = {}
    holders: dict[str, set] = defaultdict(set)
    covered, skipped = [], []

    for manager in sorted(thirteenf.MANAGERS):
        now, then = await asyncio.gather(
            _positions(manager, NOW_Q), _positions(manager, THEN_Q))
        if not now or not then:
            skipped.append(manager)
            continue
        covered.append(manager)

        for cusip, (shares_now, value_now, issuer) in now.items():
            price = value_now / shares_now if shares_now else 0.0
            delta = shares_now - then.get(cusip, (0.0,))[0]
            if delta and price:
                flow[cusip] += delta * price
                names[cusip] = issuer
                holders[cusip].add(manager)
        for cusip, (shares_then, value_then, issuer) in then.items():
            if cusip in now:
                continue
            price = value_then / shares_then if shares_then else 0.0
            if price:
                flow[cusip] -= shares_then * price
                names.setdefault(cusip, issuer)
                holders[cusip].add(manager)

    return {
        "flow": flow, "names": names, "holders": holders,
        "covered": covered, "skipped": skipped,
    }


async def congressional():
    """Transaction counts per ticker. Counts, not dollars: amounts are bands."""
    house, senate = [], []
    problems = []
    try:
        house = await congress.trades(CONGRESS_YEAR, limit=1200)
    except SourceError as exc:
        problems.append(f"House: {exc}")
    try:
        senate = await congress.senate_trades(f"{CONGRESS_YEAR}-01-01", limit=600)
    except Exception as exc:                               # noqa: BLE001
        problems.append(f"Senate: {exc}")

    rows = house + senate
    buys, sells = defaultdict(int), defaultdict(int)
    members = defaultdict(set)
    for r in rows:
        t = r["entity"]
        members[t].add(r["member"])
        (buys if r["action"] == "purchase" else sells)[t] += 1

    late = sum(1 for r in rows if (r.get("disclosure_lag_days") or 0) > 45)
    lags = sorted(r["disclosure_lag_days"] for r in rows
                  if r.get("disclosure_lag_days"))
    return {
        "buys": buys, "sells": sells, "members": members, "rows": rows,
        "house": len(house), "senate": len(senate), "problems": problems,
        "all_members": {r["member"] for r in rows},
        "late": late,
        "median_lag": lags[len(lags) // 2] if lags else None,
        "worst_lag": lags[-1] if lags else None,
        "latest_known": max((r["known_at"] for r in rows), default=None),
    }


# --------------------------------------------------------------- the matching

# 13F reports issuer names; Congress reports tickers. Joining them needs a map,
# and a hand-written one is the only honest option at this size: a fuzzy match
# between "ALPHABET INC" and GOOG would quietly pair the wrong securities.
TICKERS = {
    "ALPHABET INC": ["GOOG", "GOOGL"],
    "NVIDIA CORPORATION": ["NVDA"],
    "AMAZON COM INC": ["AMZN"],
    "APPLE INC": ["AAPL"],
    "MICROSOFT CORP": ["MSFT"],
    "BERKSHIRE HATHAWAY INC DEL": ["BRK.B", "BRK.A"],
    "META PLATFORMS INC": ["META"],
    "NETFLIX INC": ["NFLX"],
    "TESLA INC": ["TSLA"],
    "BANK AMERICA CORP": ["BAC"],
    "CHEVRON CORPORATION": ["CVX"],
    "VISA INC": ["V"],
    "MASTERCARD INCORPORATED": ["MA"],
    "MICRON TECHNOLOGY INC": ["MU"],
    "PALANTIR TECHNOLOGIES INC": ["PLTR"],
    "JOHNSON & JOHNSON": ["JNJ"],
    "ADVANCED MICRO DEVICES INC": ["AMD"],
}


# Themes are a hand-written map from issuer name to a bucket, and they are the
# one editorial act on this page. A clustering would be worse: it would move
# names between buckets on each rebuild and nobody could tell whether the theme
# rotated or the algorithm did. Substrings are matched against the 13F issuer
# name, longest first, so "TAIWAN SEMICONDUCTOR" wins over "SEMICONDUCTOR".
THEMES = {
    "Memory & storage": ["MICRON", "SANDISK", "WESTERN DIGITAL", "SEAGATE"],
    "Semi-cap & foundry": ["TAIWAN SEMICONDUCTOR", "ASML", "APPLIED MATL",
                           "LAM RESEARCH", "KLA "],
    "AI compute": ["NVIDIA", "BROADCOM", "ADVANCED MICRO", "MARVELL",
                   "SUPER MICRO", "ARM HLDGS"],
    "Megacap platforms": ["APPLE", "MICROSOFT", "ALPHABET", "AMAZON",
                          "META PLATFORMS"],
    "Banks & payments": ["BANK AMER", "BANK AMERICA", "US BANCORP", "SCHWAB",
                         "VISA", "MASTERCARD", "CAPITAL ONE", "ALLY",
                         "JPMORGAN", "WELLS FARGO", "CITIGROUP"],
    "Energy": ["CHEVRON", "OCCIDENTAL", "HESS", "EXXON", "CONOCO"],
    "Housing & builders": ["LENNAR", "NVR", "D R HORTON", "PULTE",
                           "LOUISIANA PAC"],
    "Insurance": ["CHUBB", "PROGRESSIVE", "TRAVELERS", "AON ", "MARSH"],
    "Healthcare": ["JOHNSON & JOHNSON", "ELI LILLY", "UNITEDHEALTH", "AMGEN",
                   "BRISTOL-MYERS", "MERCK", "PFIZER", "DAVITA"],
    "Consumer staples": ["COCA COLA", "PEPSICO", "KRAFT HEINZ", "PROCTER",
                         "PHILIP MORRIS", "MONDELEZ", "KEURIG", "KROGER"],
}


def theme_of(issuer: str) -> str | None:
    upper = issuer.upper()
    best = None
    for theme, needles in THEMES.items():
        for needle in needles:
            if needle in upper and (best is None or len(needle) > best[1]):
                best = (theme, len(needle))
    return best[0] if best else None


def themes(inst):
    """Net dollars traded per theme, biggest absolute move first."""
    totals: dict[str, float] = defaultdict(float)
    names: dict[str, set] = defaultdict(set)
    managers: dict[str, set] = defaultdict(set)
    for cusip, dollars in inst["flow"].items():
        issuer = inst["names"].get(cusip, "")
        theme = theme_of(issuer)
        if not theme:
            continue
        totals[theme] += dollars
        names[theme].add(issuer.title())
        managers[theme] |= inst["holders"][cusip]

    return sorted(
        ({"theme": t, "dollars": v, "names": sorted(names[t]),
          "managers": len(managers[t])} for t, v in totals.items()),
        key=lambda r: -abs(r["dollars"]),
    )


def compare(inst, cong):
    """Names where both groups traded, with the direction each one went."""
    out = []
    for issuer, tickers in TICKERS.items():
        cusips = [c for c, n in inst["names"].items() if n.upper() == issuer]
        if not cusips:
            continue
        dollars = sum(inst["flow"][c] for c in cusips)
        managers = len(set().union(*(inst["holders"][c] for c in cusips)))

        buys = sum(cong["buys"][t] for t in tickers)
        sells = sum(cong["sells"][t] for t in tickers)
        members = len(set().union(*(cong["members"][t] for t in tickers)) or set())
        if not managers or not (buys + sells):
            continue

        inst_dir = 1 if dollars > 0 else -1
        cong_dir = 1 if buys > sells else (-1 if sells > buys else 0)
        out.append({
            "issuer": issuer.title(), "dollars": dollars, "managers": managers,
            "buys": buys, "sells": sells, "members": members,
            "agree": inst_dir == cong_dir and cong_dir != 0,
            "split": cong_dir == 0,
            "verdict": "Buy" if inst_dir > 0 else "Sell",
        })
    return sorted(out, key=lambda r: -abs(r["dollars"]))


# ------------------------------------------------------------------- render

def esc(s):
    return html.escape(str(s))


def money(v):
    return f"{'+' if v > 0 else '−'}${abs(v) / 1e9:,.1f}B"


def build(inst, cong, matched, today):
    inst_asof = dt.date.fromisoformat(NOW_Q)
    next_due = min((d for d in FILING_DUE.values() if d > today), default=None)
    days = (next_due - today).days if next_due else None

    agree = [r for r in matched if r["agree"]]
    disagree = [r for r in matched if not r["agree"] and not r["split"]]

    # The headline is computed, never typed. The first draft of this page said
    # "they agree on Alphabet" as a literal, and one refresh later Congress had
    # turned net seller on Alphabet while the institutions kept buying. A
    # billboard whose claim outlives its data is the exact failure this project
    # exists to argue against.
    theme_rows = themes(inst)
    # Explicit max and min. `theme_rows` is sorted by absolute size, so walking
    # it from either end and taking the first sign match picks by magnitude in
    # one direction and against it in the other: the first draft named consumer
    # staples at -$1.1B as the outflow while banks were leaking -$12.5B.
    inflows = [t for t in theme_rows if t["dollars"] > 0]
    outflows = [t for t in theme_rows if t["dollars"] < 0]
    into = max(inflows, key=lambda t: t["dollars"], default=None)
    out_of = min(outflows, key=lambda t: t["dollars"], default=None)

    gross_in = sum(v for v in inst["flow"].values() if v > 0)
    gross_out = sum(v for v in inst["flow"].values() if v < 0)
    net = gross_in + gross_out
    widest = max(matched, key=lambda r: r["managers"], default=None)

    if into and out_of:
        claim = f"Out of {out_of['theme'].lower()}. Into {into['theme'].lower()}."
    elif into:
        claim = f"Into {into['theme'].lower()}."
    else:
        claim = "No theme moved on net this quarter."
    subclaim = (
        f"{money(net)} added on net. "
        + (f"{widest['managers']} of {len(inst['covered'])} managers moved "
           f"{widest['issuer'].split()[0]} the same way." if widest else "")
    )

    ranked = sorted(inst["flow"].items(), key=lambda kv: -kv[1])
    inst_only = [(inst["names"][c], v, len(inst["holders"][c]))
                 for c, v in ranked[:8]]
    inst_out = [(inst["names"][c], v, len(inst["holders"][c]))
                for c, v in ranked[-8:]]

    def cong_net(t):
        return cong["buys"][t] - cong["sells"][t]

    tickers = set(cong["buys"]) | set(cong["sells"])
    cong_in = sorted(tickers, key=lambda t: (-cong_net(t), -len(cong["members"][t])))[:8]
    cong_out = sorted(tickers, key=lambda t: (cong_net(t), -len(cong["members"][t])))[:8]

    def gauge(value, span, side):
        """A centre-zero bar drawn in block characters, terminal style."""
        cells = 16
        filled = max(1, round(abs(value) / span * cells)) if span else 0
        pad = "·" * (cells - filled)
        blocks = "█" * filled
        if side == "up":
            return f'<span class="gz">{pad}</span><span class="gu">{blocks}</span>'
        return f'<span class="gd">{blocks}</span><span class="gz">{pad}</span>'

    def rows_theme():
        span = max((abs(t["dollars"]) for t in theme_rows), default=1) or 1
        out = []
        for t in theme_rows:
            side = "up" if t["dollars"] > 0 else "dn"
            out.append(
                f'<tr><td class="k">{esc(t["theme"].upper())}</td>'
                f'<td class="g {side}">{gauge(t["dollars"], span, side)}</td>'
                f'<td class="v {side}">{money(t["dollars"])}</td>'
                f'<td class="m">{t["managers"]}</td></tr>')
        return "\n".join(out)

    def rows_agree():
        return "\n".join(
            f'<tr><td class="k">{esc(r["issuer"].upper()[:22])}</td>'
            f'<td class="v {"up" if r["dollars"] > 0 else "dn"}">{money(r["dollars"])}</td>'
            f'<td class="m">{r["managers"]}</td>'
            f'<td class="v {"up" if r["buys"] > r["sells"] else "dn"}">'
            f'{r["buys"] - r["sells"]:+d}</td>'
            f'<td class="m">{r["members"]}</td>'
            f'<td class="sig {"up" if r["verdict"] == "Buy" else "dn"}">'
            f'{"BUY" if r["verdict"] == "Buy" else "SELL"}</td></tr>'
            for r in agree)

    def rows_split():
        if not disagree:
            return '<tr><td class="k" colspan="6">NO DISAGREEMENT ON RECORD</td></tr>'
        return "\n".join(
            f'<tr><td class="k">{esc(r["issuer"].upper()[:22])}</td>'
            f'<td class="v {"up" if r["dollars"] > 0 else "dn"}">{money(r["dollars"])}</td>'
            f'<td class="m">{r["managers"]}</td>'
            f'<td class="v {"up" if r["buys"] > r["sells"] else "dn"}">'
            f'{r["buys"] - r["sells"]:+d}</td>'
            f'<td class="m">{r["members"]}</td>'
            f'<td class="sig amb">SPLIT</td></tr>'
            for r in disagree)

    def li(items, kind):
        if kind == "inst":
            return "\n".join(
                f'<tr><td class="k">{esc(n.upper()[:17])}</td>'
                f'<td class="v {"up" if v > 0 else "dn"}">{money(v)}</td>'
                f'<td class="m">{h}</td></tr>' for n, v, h in items)
        return "\n".join(
            f'<tr><td class="k">{esc(t)}</td>'
            f'<td class="v {"up" if cong_net(t) > 0 else "dn"}">{cong_net(t):+d}</td>'
            f'<td class="m">{len(cong["members"][t])}</td></tr>' for t in items)

    # Two more cuts, because the first layout left half the middle column empty
    # and empty space on a terminal reads as missing data rather than restraint.
    widely = sorted(
        (set(cong["buys"]) | set(cong["sells"])),
        key=lambda k: (-len(cong["members"][k]), -(cong["buys"][k] + cong["sells"][k])),
    )[:11]

    def rows_widely():
        return "\n".join(
            f'<tr><td class="k">{esc(k)}</td>'
            f'<td class="v up">{cong["buys"][k]}</td>'
            f'<td class="v dn">{cong["sells"][k]}</td>'
            f'<td class="v {"up" if cong_net(k) > 0 else "dn"}">{cong_net(k):+d}</td>'
            f'<td class="m">{len(cong["members"][k])}</td></tr>' for k in widely)

    late_rows = sorted(
        (r for r in cong["rows"] if (r.get("disclosure_lag_days") or 0) > 45),
        key=lambda r: -r["disclosure_lag_days"])[:7]

    def rows_late():
        if not late_rows:
            return '<tr><td class="k" colspan="4">NO FILINGS PAST THE DEADLINE</td></tr>'
        return "\n".join(
            f'<tr><td class="k">{esc((r.get("member") or "").upper()[:22])}</td>'
            f'<td class="k">{esc(r["entity"])}</td>'
            f'<td class="v dn">{r["disclosure_lag_days"]}D</td>'
            f'<td class="m">{esc(r["observed_at"][2:])}</td></tr>' for r in late_rows)

    # The mark is a tape strip with three prints on it, the middle one long.
    # It reads as ticker tape at 18px and as an "A" counter at 200px, which is
    # what a lockup has to do. Drawn inline so it inherits currentColor and can
    # never load late, half-styled, or not at all.
    logo = (
        '<svg class="mk" viewBox="0 0 26 26" aria-hidden="true">'
        '<path d="M2 5 h22 v16 h-22 z" fill="none" stroke="currentColor"'
        ' stroke-width="1.6"/>'
        '<path d="M7 17 V11" stroke="currentColor" stroke-width="2.4"/>'
        '<path d="M13 19 V7" stroke="currentColor" stroke-width="2.4"/>'
        '<path d="M19 17 V13" stroke="currentColor" stroke-width="2.4"/>'
        '</svg>')

    crawl = (
        f"AMOUNTS DISCLOSED BY CONGRESS ARE BANDS, NOT FIGURES — DIRECTION AND "
        f"COUNT ARE THE ONLY HONEST MEASURES ▪ "
        f"{len(cong['all_members'])} MEMBERS IS NOT CONGRESS, "
        f"{len(inst['covered'])} MANAGERS IS NOT THE MARKET ▪ "
        f"INSTITUTIONAL FIGURES ARE SHARE-COUNT CHANGES PRICED AT THE LATER "
        f"QUARTER, SO APPRECIATION IS NOT A PURCHASE ▪ "
        f"13F LANDS 45 DAYS AFTER THE QUARTER ▪ "
        f"{cong['late']} OF {len(cong['rows']):,} CONGRESSIONAL TRANSACTIONS "
        f"({cong['late'] / max(len(cong['rows']), 1):.0%}) WERE DISCLOSED PAST THE "
        f"45-DAY STATUTORY DEADLINE, WORST BY {cong['worst_lag']} DAYS ▪ "
        f"NOTHING HERE IS ADVICE, AND EVERY POSITION WAS PUBLIC BEFORE YOU READ IT ▪ "
        f"REPORTS OBTAINED UNDER THE ETHICS IN GOVERNMENT ACT, WHICH RESTRICTS "
        f"COMMERCIAL USE ▪ "
    )

    return f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>APE TAPE — VINTAGE</title>
<meta name="description" content="Ape Tape: two independent groups of money, 13F institutions and members of Congress, on one screen. Everything here was late by law before you read it.">
<style>
:root{{
  --bg:#000; --ink:#e6e6e6; --amber:#ffa028; --amber-dim:#7a4d12;
  --line:#241a08; --rule:#3a2a10; --up:#22e07a; --dn:#ff4d3d;
  --grey:#6c6c6c;
  --mono:"IBM Plex Mono",ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --fs:clamp(11px,1.62vh,15px);
}}
*{{box-sizing:border-box;border-radius:0!important}}
html,body{{height:100%;overflow:hidden}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--mono);
  font-size:var(--fs);line-height:1.35;-webkit-font-smoothing:antialiased;
  letter-spacing:.01em}}
.term{{height:100%;display:flex;flex-direction:column;padding:0 6px 0}}

/* ---------- command bar ---------- */
.cmd{{display:flex;align-items:center;gap:12px;padding:5px 6px;
  border-bottom:1px solid var(--rule);white-space:nowrap;overflow:hidden}}
.lock{{display:inline-flex;align-items:center;gap:7px;color:var(--amber);
  text-decoration:none;padding:1px 9px 1px 0;border-right:1px solid var(--rule)}}
.lock .mk{{width:1.55em;height:1.55em;display:block;flex:none}}
.wm{{font-weight:700;letter-spacing:.2em;font-size:1.12em;line-height:1}}
.wm i{{font-style:normal;color:var(--ink);letter-spacing:.2em}}
.lock:hover{{color:#ffbe5e}}
.cmd .go{{color:var(--bg);background:var(--amber);padding:1px 7px;font-weight:700}}
.cmd .q{{color:var(--grey)}}
.cmd .rt{{margin-left:auto;color:var(--amber-dim)}}
.cmd .rt b{{color:var(--amber);font-weight:400}}

/* ---------- function keys ---------- */
.fn{{display:flex;gap:1px;padding:3px 0 4px}}
.fn span{{background:#120c03;border:1px solid var(--line);color:var(--amber);
  padding:2px 9px;letter-spacing:.1em}}
.fn span b{{color:var(--bg);background:var(--amber);padding:0 3px;margin-right:5px;
  font-weight:700}}
.fn .spacer{{flex:1;background:none;border:0}}

/* ---------- headline band ---------- */
.band{{border:1px solid var(--rule);border-left:3px solid var(--amber);
  padding:6px 10px;margin-bottom:4px;display:flex;align-items:baseline;
  gap:16px;flex-wrap:wrap}}
.band .hl{{font-size:clamp(12px,2.5vh,26px);letter-spacing:-.01em;color:var(--ink)}}
.band .hl em{{font-style:normal;color:var(--amber)}}
.band .sb{{color:var(--grey);margin-left:auto}}
.band .sb b{{color:var(--ink);font-weight:400}}

/* ---------- grid ---------- */
.grid{{flex:1;min-height:0;display:grid;gap:4px;
  grid-template-columns:1fr 1.2fr 1.02fr;grid-template-rows:1fr}}
.col{{display:flex;flex-direction:column;gap:4px;min-height:0}}
.box{{border:1px solid var(--rule);display:flex;flex-direction:column;
  min-height:0;overflow:hidden}}
.box.grow{{flex:1}}
.box.fit{{flex:0 0 auto}}
.hd{{background:#140d04;color:var(--amber);padding:2px 7px;letter-spacing:.16em;
  border-bottom:1px solid var(--line);display:flex;gap:8px;white-space:nowrap}}
.hd s{{text-decoration:none;color:var(--amber-dim);margin-left:auto}}
.pad{{padding:3px 7px 4px;overflow:hidden;min-height:0}}

table{{width:100%;border-collapse:collapse;table-layout:fixed;
  font-family:var(--mono);font-size:var(--fs)}}
th{{color:var(--amber-dim);text-align:right;font-weight:400;letter-spacing:.1em;
  padding:2px 5px;border-bottom:1px solid var(--line)}}
th.l{{text-align:left}}
td{{padding:2.5px 6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
tr+tr td{{border-top:1px solid #120d05}}
td.k{{color:var(--ink);letter-spacing:.02em}}
td.v{{text-align:right;font-variant-numeric:tabular-nums;width:74px}}
td.m{{text-align:right;color:var(--grey);width:26px}}
td.sig{{text-align:right;width:40px;font-weight:700}}
.up{{color:var(--up)}} .dn{{color:var(--dn)}} .amb{{color:var(--amber)}}
td.g{{width:50%;letter-spacing:-.5px;text-align:center;
  text-overflow:clip;overflow:visible}}
.gz{{color:#1d1d1d}} .gu{{color:var(--up)}} .gd{{color:var(--dn)}}

/* ---------- stat cells ---------- */
.cells{{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line)}}
.cell{{background:#0a0703;padding:4px 7px}}
.cell i{{font-style:normal;display:block;color:var(--amber-dim);letter-spacing:.12em}}
.cell b{{display:block;font-size:clamp(10px,1.75vh,17px);font-weight:400;
  font-variant-numeric:tabular-nums;margin-top:1px}}
.cell s{{display:block;text-decoration:none;color:var(--grey)}}

/* ---------- ticker ---------- */
.tick{{border-top:1px solid var(--rule);overflow:hidden;white-space:nowrap;
  padding:3px 0;color:var(--amber-dim)}}
.tick div{{display:inline-block;padding-left:100%;
  animation:crawl 90s linear infinite}}
@keyframes crawl{{from{{transform:translateX(0)}}to{{transform:translateX(-100%)}}}}
@media(prefers-reduced-motion:reduce){{.tick div{{animation:none;padding-left:0}}}}

@media(max-width:900px){{
  html,body{{overflow:auto}}
  .grid{{grid-template-columns:1fr;grid-template-rows:none}}
  .box{{max-height:none}}
  .fn{{flex-wrap:wrap}}
}}
</style>

<div class="term">

  <div class="cmd">
    <a class="lock" href="https://github.com/RezaSoleymanifar/vintage">
      {logo}<span class="wm">APE<i>TAPE</i></span></a>
    <span class="go">GO</span>
    <span class="q">FLOW &lt;EQUITY&gt; 13F/STOCK-ACT XCOMPARE</span>
    <span class="rt">SRC <b>SEC · HOUSE CLERK · SENATE EFD</b> &nbsp;|&nbsp;
      BUILD <b>{today:%d-%b-%Y}</b> &nbsp;|&nbsp; <b>LATE BY LAW</b></span>
  </div>

  <div class="fn">
    <span><b>F1</b>THEMES</span>
    <span><b>F2</b>AGREED</span>
    <span><b>F3</b>SPLIT</span>
    <span><b>F4</b>SOLO</span>
    <span><b>F5</b>CLOCKS</span>
    <span><b>F6</b>CROWDED</span>
    <span><b>F7</b>LATE</span>
    <span class="spacer"></span>
    <span><b>N</b>{len(inst['flow']):,} NAMES</span>
    <span><b>M</b>{len(inst['covered'])} MGRS</span>
    <span><b>C</b>{len(cong['all_members'])} MEMBERS</span>
  </div>

  <div class="band">
    <span class="hl">OUT OF <em>{esc(out_of['theme'].upper() if out_of else '—')}</em>
      &nbsp;&nbsp;INTO <em>{esc(into['theme'].upper() if into else '—')}</em></span>
    <span class="sb">NET <b class="{'up' if net > 0 else 'dn'}">{money(net)}</b>
      &nbsp;·&nbsp; BOT <b class="up">{money(gross_in)}</b>
      &nbsp;·&nbsp; SLD <b class="dn">{money(gross_out)}</b></span>
  </div>

  <div class="grid">

    <div class="col">
      <div class="box fit">
        <div class="hd">F1 · THEME FLOW<s>NET SHARE-COUNT CHANGE, PRICED {NOW_Q}</s></div>
        <div class="pad"><table>
          <tr><th class="l">THEME</th><th>&#8592; SOLD &nbsp; BOUGHT &#8594;</th>
              <th>USD</th><th>MGR</th></tr>
          {rows_theme()}
        </table></div>
      </div>
      <div class="box grow">
        <div class="hd">F6 · CONGRESS, MOST MEMBERS TRADING<s>ONE NAME, MANY DESKS</s></div>
        <div class="pad"><table>
          <tr><th class="l">TICKER</th><th>BUY</th><th>SELL</th><th>NET</th><th>MBR</th></tr>
          {rows_widely()}
        </table></div>
      </div>
    </div>

    <div class="col">
      <div class="box fit">
        <div class="hd">F2 · BOTH GROUPS AGREED<s>{len(agree)} NAMES</s></div>
        <div class="pad"><table>
          <tr><th class="l">NAME</th><th>INST</th><th>MGR</th>
              <th>CONG</th><th>MBR</th><th>SIG</th></tr>
          {rows_agree()}
        </table></div>
      </div>
      <div class="box fit">
        <div class="hd">F3 · THEY SPLIT<s>{len(disagree)} NAMES</s></div>
        <div class="pad"><table>
          <tr><th class="l">NAME</th><th>INST</th><th>MGR</th>
              <th>CONG</th><th>MBR</th><th>SIG</th></tr>
          {rows_split()}
        </table></div>
      </div>
      <div class="box grow">
        <div class="hd">F7 · PAST THE STATUTORY DEADLINE
          <s>{cong['late']} OF {len(cong['rows']):,} · STOCK ACT ALLOWS 45D</s></div>
        <div class="pad"><table>
          <tr><th class="l">MEMBER</th><th class="l">TKR</th><th>LAG</th><th>TRADED</th></tr>
          {rows_late()}
        </table></div>
      </div>
    </div>

    <div class="col">
      <div class="box">
        <div class="hd">F5 · CLOCKS</div>
        <div class="cells">
          <div class="cell"><i>INST AS OF</i><b>{inst_asof:%d-%b-%y}</b>
            <s>FILED {NOW_Q[:4]}-05-15</s></div>
          <div class="cell"><i>CONG AS OF</i><b>{esc((cong['latest_known'] or '—')[5:])}</b>
            <s>{len(cong['rows']):,} TRANSACTIONS</s></div>
          <div class="cell"><i>INST NEXT MOVE</i><b class="amb">{next_due:%d-%b-%y}</b>
            <s>{days}D · Q2 13F DUE</s></div>
          <div class="cell"><i>CONG MOVES</i><b>CONTINUOUS</b>
            <s>MEDIAN {cong['median_lag']}D LAG</s></div>
        </div>
      </div>
      <div class="box grow">
        <div class="hd">F4 · INSTITUTIONS ONLY<s>NOT TRADED BY CONGRESS</s></div>
        <div class="pad"><table>
          {li(inst_only[:4], 'inst')}
          {li(inst_out[:4], 'inst')}
        </table></div>
      </div>
      <div class="box grow">
        <div class="hd">F4 · CONGRESS ONLY<s>NET TRANSACTION COUNT</s></div>
        <div class="pad"><table>
          {li(cong_in[:4], 'cong')}
          {li(cong_out[:4], 'cong')}
        </table></div>
      </div>
    </div>

  </div>

  <div class="tick"><div>{esc(crawl) * 2}</div></div>
</div>
"""


async def main():
    today = dt.date.today()
    print("reading 13F...", flush=True)
    inst = await institutional()
    print(f"  {len(inst['covered'])} managers, skipped {len(inst['skipped'])}", flush=True)
    print("reading Congress...", flush=True)
    cong = await congressional()
    print(f"  {cong['house']} House + {cong['senate']} Senate rows", flush=True)

    matched = compare(inst, cong)
    page = build(inst, cong, matched, today)

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "docs", "flows.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"wrote {out} ({len(page):,} bytes)")
    print(f"  matched {len(matched)} names, "
          f"{sum(1 for m in matched if m['agree'])} agreeing")


if __name__ == "__main__":
    asyncio.run(main())
