"""The flow billboard: where two independent groups of money actually moved.

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

    def rows_agree():
        return "\n".join(
            f'<tr><td class="n">{esc(r["issuer"])}</td>'
            f'<td class="num {"up" if r["dollars"] > 0 else "dn"}">{money(r["dollars"])}'
            f'<s>{r["managers"]} of {len(inst["covered"])} managers</s></td>'
            f'<td class="num {"up" if r["buys"] > r["sells"] else "dn"}">'
            f'{r["buys"] - r["sells"]:+d} net<s>{r["members"]} members</s></td>'
            f'<td class="v {"up" if r["verdict"] == "Buy" else "dn"}">{r["verdict"]}</td></tr>'
            for r in agree)

    def rows_split():
        if not disagree:
            return '<tr><td colspan="4" class="none">None. Both groups went the same way on every overlapping name.</td></tr>'
        return "\n".join(
            f'<tr><td class="n">{esc(r["issuer"])}</td>'
            f'<td class="num {"up" if r["dollars"] > 0 else "dn"}">{money(r["dollars"])}'
            f'<s>{r["managers"]} managers</s></td>'
            f'<td class="num {"up" if r["buys"] > r["sells"] else "dn"}">'
            f'{r["buys"] - r["sells"]:+d} net<s>{r["members"]} members</s></td>'
            f'<td class="v split">Split</td></tr>'
            for r in disagree)

    def rows_theme():
        span = max((abs(t["dollars"]) for t in theme_rows), default=1) or 1
        out = []
        for t in theme_rows:
            # Halved: the rail is a diverging axis with zero at its midpoint, so
            # the widest bar reaches one edge, not one and a half.
            pct = abs(t["dollars"]) / span * 50
            side = "up" if t["dollars"] > 0 else "dn"
            bar = (f'<i class="bar {side}" style="width:{pct:.1f}%"></i>')
            out.append(
                f'<tr><td class="n">{esc(t["theme"])}'
                f'<s>{esc(", ".join(n[:22] for n in t["names"][:4]))}'
                f'{" …" if len(t["names"]) > 4 else ""}</s></td>'
                f'<td class="track"><div class="rail {side}">{bar}</div></td>'
                f'<td class="num {side}">{money(t["dollars"])}'
                f'<s>{t["managers"]} managers</s></td></tr>')
        return "\n".join(out)

    def li(items, kind):
        if kind == "inst":
            return "\n".join(
                f'<li><b>{esc(n.title()[:28])}</b><span>{money(v)} · {h} mgrs</span></li>'
                for n, v, h in items)
        return "\n".join(
            f'<li><b>{esc(t)}</b><span>{cong_net(t):+d} net · '
            f'{len(cong["members"][t])} members</span></li>' for t in items)

    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Where the money moved — Vintage</title>
<meta name="description" content="Two independent groups of money, 13F institutions and members of Congress, compared on the names they both traded. Built from primary filings, with every date shown.">
<style>
:root{{
  --bg:#0b0f16; --panel:#0d1420; --line:#1f2b3a; --ink:#e8f1ec;
  --dim:#5f7a8c; --green:#35e08a; --red:#ff6b5e; --amber:#ffc46b;
  --mono:"IBM Plex Mono",ui-monospace,"SF Mono",Menlo,Consolas,monospace;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--mono);
  line-height:1.5;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1080px;margin:0 auto;padding:40px 20px 80px}}
h1{{font-size:clamp(26px,4.4vw,46px);line-height:1.12;margin:0 0 14px;letter-spacing:-.02em}}
h1 em{{font-style:normal;color:var(--green)}}
h1 small{{display:block;font-size:15px;color:var(--dim);margin-top:12px;letter-spacing:0}}
h2{{font-size:13px;letter-spacing:.22em;text-transform:uppercase;color:var(--dim);
  font-weight:400;margin:44px 0 14px;border-bottom:1px solid var(--line);padding-bottom:9px}}
.lede{{color:var(--dim);font-size:15px;max-width:62ch;margin:0 0 26px}}
.clocks{{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px;margin:0 0 10px}}
.clock{{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:14px 16px}}
.clock i{{font-style:normal;display:block;font-size:11px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--dim);margin-bottom:7px}}
.clock b{{display:block;font-size:19px}}
.clock s{{display:block;text-decoration:none;color:var(--dim);font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th{{text-align:left;font-weight:400;font-size:11px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--dim);padding:0 10px 9px;border-bottom:1px solid var(--line)}}
td{{padding:13px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
td.n{{font-size:16px}}
.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.num s,.v s{{display:block;text-decoration:none;color:var(--dim);font-size:11px;margin-top:3px}}
.up{{color:var(--green)}} .dn{{color:var(--red)}}
.v{{text-align:right;font-size:15px}}
.v.split{{color:var(--amber)}}
.none{{color:var(--dim);text-align:left}}
.cols{{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:20px}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px}}
.card h3{{margin:0 0 12px;font-size:12px;letter-spacing:.16em;text-transform:uppercase;
  color:var(--dim);font-weight:400}}
ul{{list-style:none;margin:0;padding:0}}
li{{display:flex;justify-content:space-between;gap:14px;padding:7px 0;
  border-bottom:1px solid rgba(31,43,58,.55);font-size:13px}}
li:last-child{{border-bottom:0}}
li span{{color:var(--dim);white-space:nowrap;font-size:12px}}
.flowstrip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
  gap:12px;margin:30px 0 4px}}
.flowstrip div{{background:var(--panel);border:1px solid var(--line);
  border-radius:11px;padding:14px 16px}}
.flowstrip i{{font-style:normal;display:block;font-size:11px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--dim);margin-bottom:6px}}
.flowstrip b{{font-size:23px;font-variant-numeric:tabular-nums}}
table.themes td{{padding:11px 10px}}
table.themes td.num{{width:130px}}
.track{{width:38%;padding:11px 18px}}
.rail{{height:9px;border-radius:5px;background:rgba(31,43,58,.7);position:relative}}
.bar{{position:absolute;top:0;height:9px;border-radius:5px;display:block}}
.rail.up .bar{{left:50%;background:var(--green)}}
.rail.dn .bar{{right:50%;background:var(--red)}}
.rail::after{{content:"";position:absolute;left:50%;top:-4px;width:1px;height:17px;
  background:var(--line)}}
td.n s{{display:block;text-decoration:none;color:var(--dim);font-size:11.5px;margin-top:4px}}
.foot{{color:var(--dim);font-size:12.5px;margin:12px 0 0;max-width:70ch}}
.foot code{{color:var(--ink)}}
.warn{{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--amber);
  border-radius:11px;padding:18px 22px;margin-top:14px}}
.warn ul li{{display:list-item;border:0;padding:5px 0;color:var(--dim);font-size:13.5px}}
.warn ul{{padding-left:18px;list-style:disc}}
.warn b{{color:var(--ink)}}
footer{{margin-top:52px;padding-top:20px;border-top:1px solid var(--line);
  color:var(--dim);font-size:12.5px}}
footer a{{color:var(--green);text-decoration:none}}
@media(max-width:620px){{td.n{{font-size:14px}} .num,.v{{font-size:13px}}}}
</style>

<div class="wrap">
<h1>Two groups of money.<br><em>{esc(claim)}</em><br><small>{esc(subclaim)}</small></h1>
<p class="lede">Institutional managers file Form 13F once a quarter. Members of Congress
file a report every time they trade. Neither can see the other's filing before it lands.
Below is every name both groups touched.</p>

<div class="clocks">
  <div class="clock"><i>Institutions as of</i><b>{inst_asof:%d %b %Y}</b>
    <s>{len(inst['covered'])} managers · filed {NOW_Q[:4]}-05-15</s></div>
  <div class="clock"><i>Congress as of</i><b>{esc(cong['latest_known'] or '—')}</b>
    <s>{len(cong['all_members'])} members · {len(cong['rows']):,} transactions</s></div>
  <div class="clock"><i>Institutional data next moves</i>
    <b>{next_due:%d %b %Y}</b><s>{days} days · Q2 2026 13F deadline</s></div>
  <div class="clock"><i>Congressional data moves</i><b>Continuously</b>
    <s>median {cong['median_lag']}-day disclosure lag</s></div>
</div>

<div class="flowstrip">
  <div><i>Gross bought</i><b class="up">{money(gross_in)}</b></div>
  <div><i>Gross sold</i><b class="dn">{money(gross_out)}</b></div>
  <div><i>Net</i><b class="{'up' if net > 0 else 'dn'}">{money(net)}</b></div>
  <div><i>Names moved</i><b>{len(inst['flow']):,}</b></div>
</div>

<h2>Which themes the money left, and where it went</h2>
<table class="themes"><tbody>
{rows_theme()}
</tbody></table>
<p class="foot">Themes are a fixed map from issuer name to bucket, listed in
<code>tools/build_flows.py</code>. A clustering would reshuffle names between
rebuilds and you could not tell a rotation from an algorithm change.</p>

<h2>Where both groups went the same way</h2>
<table><thead><tr><th>Name</th><th class="num">{len(inst['covered'])} institutions</th>
<th class="num">{len(cong['all_members'])} members of Congress</th><th class="v">Verdict</th></tr></thead>
<tbody>
{rows_agree()}
</tbody></table>

<h2>Where they disagreed</h2>
<table><thead><tr><th>Name</th><th class="num">Institutions</th>
<th class="num">Congress</th><th class="v"></th></tr></thead>
<tbody>
{rows_split()}
</tbody></table>

<h2>What only one group traded</h2>
<div class="cols">
  <div class="card"><h3>Institutions bought</h3><ul>{li(inst_only, 'inst')}</ul></div>
  <div class="card"><h3>Institutions sold</h3><ul>{li(inst_out, 'inst')}</ul></div>
  <div class="card"><h3>Congress bought</h3><ul>{li(cong_in, 'cong')}</ul></div>
  <div class="card"><h3>Congress sold</h3><ul>{li(cong_out, 'cong')}</ul></div>
</div>

<h2>What this is not</h2>
<div class="warn"><ul>
<li><b>{len(cong['all_members'])} members is not Congress</b>, and
{len(inst['covered'])} managers is not the market. Both are the subset that filed
comparable reports in this window.</li>
<li><b>Congressional amounts are bands</b>, not figures. Direction and count are
the only honest measures, so no dollar total is shown for that half.</li>
<li><b>Institutional figures are share-count changes</b> priced at the later
quarter, so a position that merely appreciated does not appear as a purchase.</li>
<li><b>Everything here was late by construction.</b> 13F lands 45 days after the
quarter; {cong['late']} of {len(cong['rows']):,} congressional transactions
({cong['late'] / max(len(cong['rows']), 1):.0%}) were disclosed past the 45-day
statutory deadline, the worst by {cong['worst_lag']} days.</li>
<li><b>Nothing here is advice</b>, and every position was public knowledge before
you read it.</li>
</ul></div>

<footer>
Built {today:%d %B %Y} from SEC Form 13F, House STOCK Act periodic transaction
reports and Senate EFD, by <a href="https://github.com/RezaSoleymanifar/vintage">Vintage</a>.
Reports obtained under the Ethics in Government Act, which restricts commercial use.
Regenerate with <code>python tools/build_flows.py</code>.
</footer>
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
