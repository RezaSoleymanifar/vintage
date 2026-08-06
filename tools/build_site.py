"""Generate docs/index.html (a diagram-first landing page) and docs/reel.html.

The page makes one claim: Vintage federates the free, point-in-time financial
data of the web. Three architecture diagrams carry almost all of the argument,
so the prose can stay short. Each diagram is inline SVG with CSS-driven motion.
No runtime JS, no libraries, sharp at any size, and a frame grabber can scrub it
deterministically.

  1. Federation: scattered sources, through four pipeline stages, to six verbs.
  2. Point-in-time: an as-of wall sweeping a timeline, lighting rows as it passes.
  3. Honesty: 41 specs piling into a trial ledger, collapsing the Sharpe.

The hero terminal is the same keyframe trick, and is how assets/demo.gif is made.
The four-scene showcase reel now lives on its own page (docs/reel.html) so the
landing page stays short while the GIF pipeline keeps working.

    uv run python tools/build_site.py
"""

from __future__ import annotations

import html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import showcase
from dataclasses import dataclass, field

# --------------------------------------------------------------- the script

LOOP = 19.0  # seconds for one full pass


@dataclass
class Typed:
    """A line the user types, revealed character by character."""
    at: float
    text: str
    prompt: str = "❯"
    prompt_class: str = "p-user"
    typing: float = 1.9  # seconds to finish typing


@dataclass
class Out:
    """A line the terminal prints, revealed all at once."""
    at: float
    text: str = ""
    cls: str = ""
    indent: int = 0
    cells: list[tuple[str, str]] = field(default_factory=list)


SCRIPT: list = [
    Typed(0.3, "claude mcp add vintage -s user -- uvx vintage-mcp", prompt="$", prompt_class="p-shell", typing=1.8),
    Out(2.5, "connected · sec · fred · dartmouth · openap · coinbase · finra", cls="ok"),

    Typed(3.6, "backtest 12-1 momentum on the dow 30 since 2010", typing=1.7),
    Out(5.7, "reading 30 tickers from yahoo-finance, 3,914 sessions", cls="dim", indent=1),
    Out(6.1, "panel indexed on known_at, lookahead structurally impossible", cls="dim", indent=1),
    Out(6.6, cells=[("annualized return", "14.8%"), ("volatility", "17.1%"), ("turnover cost", "−40 bps/yr")]),
    Out(7.2, cells=[("sharpe", "2.14")], cls="big"),

    Typed(8.2, "try short-term reversal instead", typing=1.3),
    Out(9.9, cells=[("sharpe", "1.87")], cls="mid"),

    Typed(10.7, "and low volatility", typing=1.1),
    Out(12.1, cells=[("sharpe", "2.31")], cls="mid"),

    Out(13.0, "honesty report", cls="rule"),
    Out(13.3, cells=[("specs tried this session", "41")], indent=1),
    Out(13.7, cells=[("sharpe noise would produce", "2.29")], indent=1),
    Out(14.1, cells=[("deflated sharpe probability", "0.09")], cls="bad", indent=1),
    Out(14.8, "after 41 trials, a sharpe this high is what noise produces.", cls="verdict", indent=1),
    Out(15.6, "the terminal you pay for does not tell you this.", cls="kicker", indent=1),
]

# ------------------------------------------------------------------ codegen


def pct(t: float) -> float:
    return max(0.0, min(100.0, t / LOOP * 100.0))


def build_terminal() -> tuple[str, str]:
    """Return (html, css) for the animated session."""
    rows: list[str] = []
    css: list[str] = []

    typed_times = [e.at for e in SCRIPT if isinstance(e, Typed)]

    for i, ev in enumerate(SCRIPT):
        if isinstance(ev, Typed):
            n = len(ev.text)
            # The cursor sits on this line until the next typed line takes over.
            nxt = next((t for t in typed_times if t > ev.at), LOOP - 0.4)

            css.append(
                f"@keyframes a{i}{{0%,{pct(ev.at - 0.05):.3f}%{{opacity:0}}"
                f"{pct(ev.at):.3f}%,100%{{opacity:1}}}}"
            )
            css.append(
                f"@keyframes w{i}{{0%,{pct(ev.at):.3f}%{{width:0}}"
                f"{pct(ev.at + ev.typing):.3f}%,100%{{width:{n}ch}}}}"
            )
            css.append(
                f"@keyframes c{i}{{0%,{pct(ev.at - 0.05):.3f}%{{visibility:hidden}}"
                f"{pct(ev.at):.3f}%,{pct(nxt - 0.15):.3f}%{{visibility:visible}}"
                f"{pct(nxt - 0.1):.3f}%,100%{{visibility:hidden}}}}"
            )
            css.append(f".r{i}{{animation:a{i} {LOOP}s infinite}}")
            css.append(f".t{i}{{animation:w{i} {LOOP}s steps({n},end) infinite}}")
            css.append(f".k{i}{{animation:c{i} {LOOP}s infinite,blink .9s steps(2,end) infinite}}")

            rows.append(
                f'<div class="row r{i}">'
                f'<span class="prompt {ev.prompt_class}">{ev.prompt}</span>'
                f'<span class="typed t{i}">{html.escape(ev.text)}</span>'
                f'<span class="caret k{i}"></span>'
                f"</div>"
            )
        else:
            css.append(
                f"@keyframes a{i}{{0%,{pct(ev.at - 0.05):.3f}%{{opacity:0;transform:translateY(3px)}}"
                f"{pct(ev.at + 0.18):.3f}%,100%{{opacity:1;transform:none}}}}"
            )
            css.append(f".r{i}{{animation:a{i} {LOOP}s infinite}}")

            classes = " ".join(c for c in ["row", f"r{i}", ev.cls, f"in{ev.indent}" if ev.indent else ""] if c)
            if ev.cells:
                inner = "".join(
                    f'<span class="k">{html.escape(k)}</span><span class="v">{html.escape(v)}</span>'
                    for k, v in ev.cells
                )
                rows.append(f'<div class="{classes} kv">{inner}</div>')
            elif ev.cls == "rule":
                rows.append(f'<div class="{classes}"><i></i>{html.escape(ev.text)}<i></i></div>')
            elif ev.cls == "ok":
                rows.append(f'<div class="{classes}"><b>✓</b>{html.escape(ev.text)}</div>')
            else:
                rows.append(f'<div class="{classes}">{html.escape(ev.text)}</div>')

    return "\n        ".join(rows), "\n".join(css)


# ------------------------------------------------------- diagram primitives

DIA_CSS: list[str] = []  # keyframes generated per element, appended to the page


def reveal(name: str, at: float, dur: float, dim: float = 0.14) -> str:
    """A keyframe that holds an element ghosted, then lights it at `at` percent."""
    a = max(at - 0.4, 0.0)
    DIA_CSS.append(
        f"@keyframes {name}{{0%,{a:.2f}%{{opacity:{dim}}}"
        f"{at:.2f}%,100%{{opacity:1}}}}"
    )
    return f"{name} {dur}s linear infinite"


def grow(name: str, at: float, dur: float, w: float) -> str:
    """A keyframe that keeps a bar at zero width, then snaps it open at `at`."""
    DIA_CSS.append(
        f"@keyframes {name}{{0%,{at:.2f}%{{width:0}}"
        f"{min(at + 3, 100):.2f}%,100%{{width:{w:.1f}px}}}}"
    )
    return f"{name} {dur}s linear infinite"


def card(x, y, w, h, cls="d-card") -> str:
    return f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="11"/>'


def txt(x, y, s, cls, anchor="start") -> str:
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    return f'<text class="{cls}" x="{x}" y="{y}"{a}>{s}</text>'


# ---------------------------------------------------- diagram 1: federation

# Every source, as a glyph with what it actually holds. This was four grouped
# text panels naming nine sources, which both undercounted the breadth by half
# and buried it in prose. One orb per source shows the spread at a glance and
# still says what each one carries.
#   (glyph, name, what it holds, group)
UNIVERSE = [
    ("gov",      "SEC XBRL",       "every tagged concept",   "REGULATORS"),
    ("ledger",   "SEC filings",    "8-K, 10-K, Form 4",      "REGULATORS"),
    ("stack",    "SEC 13F",        "institutional holdings", "REGULATORS"),
    ("fall",     "SEC Form 25",    "36,830 delistings",      "REGULATORS"),
    ("scatter",  "XBRL frames",    "6,289 filers at once",   "REGULATORS"),
    ("shield",   "FINRA",          "daily short volume",     "REGULATORS"),
    ("wall",     "CFTC",           "weekly positioning",     "REGULATORS"),

    ("coin",     "FRED",           "800k series, vintages",  "CENTRAL BANKS"),
    ("series",   "US Treasury",    "14-tenor yield curve",   "CENTRAL BANKS"),
    ("calendar", "ECB",            "FX rates since 1999",    "CENTRAL BANKS"),
    ("clock",    "BLS",            "CPI, payrolls, JOLTS",   "CENTRAL BANKS"),
    ("funnel",   "BEA",            "the national accounts",  "CENTRAL BANKS"),

    ("prompt",   "Yahoo",          "daily OHLCV, decades",   "MARKETS"),
    ("flask",    "CBOE",           "VIX and the vol family", "MARKETS"),
    ("install",  "Coinbase",       "crypto, never restated", "MARKETS"),

    ("school",   "Ken French",     "factors from July 1926", "ACADEMIA"),
    ("zero",     "Open Source AP", "331 published claims",   "ACADEMIA"),
    ("ask",      "ApeWisdom",      "forum mention ranks",    "ACADEMIA"),
]

GROUP_ORDER = ["REGULATORS", "CENTRAL BANKS", "MARKETS", "ACADEMIA"]

STAGES = [
    ("resolve", "AAPL &middot; 0000320193 &middot; &ldquo;Apple Inc&rdquo;",
     "&rarr; one entity key every source accepts"),
    ("normalize", "four wire formats, ten field vocabularies",
     "&rarr; one schema, one unit convention"),
    ("stamp vintage", "every row gets observed_at + known_at",
     "no honest date &rarr; flagged UNKNOWN_VINTAGE"),
    ("index on known_at", "the panel is point-in-time by construction",
     "there is no flag that turns this off"),
]

VERB_NAMES = ["resolve", "discover", "fetch", "events", "backtest", "benchmark"]


def diagram_federation() -> str:
    p: list[str] = []
    p.append('<svg class="dia" viewBox="0 0 1160 600" role="img" '
             'aria-label="Scattered free data sources federated through Vintage into six verbs">')

    p.append(txt(20, 40, "THE WEB &middot; 18 FREE SOURCES", "d-h"))
    p.append(txt(380, 44, "VINTAGE &middot; THE FEDERATION LAYER", "d-h g"))
    p.append(txt(830, 44, "ONE INTERFACE", "d-h"))

    # ---- left: every source as a glyph, grouped by who publishes it
    # Two columns per group. Eighteen orbs stacked in one column needed a
    # canvas half again as tall, which broke the layout this page is built
    # around: everything on one screen, nothing scrolls.
    y = 66
    group_mid: dict[str, float] = {}
    for gi, group in enumerate(GROUP_ORDER):
        members = [u for u in UNIVERSE if u[3] == group]
        top = y
        p.append(txt(20, y, group, "d-ct"))
        y += 10
        rows = (len(members) + 1) // 2
        for j, (glyph, name, holds, _g) in enumerate(members):
            col, row = j % 2, j // 2
            cx = 22 + col * 168
            cy = y + row * 34
            p.append(f'<g class="d-orb" transform="translate({cx},{cy})" '
                     f'style="animation-delay:{(gi * 5 + j) * -0.37:.2f}s">'
                     f'<circle class="d-orbring" cx="10" cy="10" r="11.5"/>'
                     f'<g transform="translate(-2,-2)">{icon(glyph, 24)}</g></g>')
            p.append(txt(cx + 28, cy + 9, name, "d-it"))
            p.append(txt(cx + 28, cy + 21, holds, "d-fn"))
        y += rows * 34 + 10
        group_mid[group] = (top + y) / 2 - 8

    # ---- middle: the pipeline
    p.append('<rect class="d-pipe" x="380" y="70" width="380" height="490" rx="14"/>')
    for i, (name, l1, l2) in enumerate(STAGES):
        y = 96 + i * 96
        p.append(card(400, y, 340, 84, "d-stage"))
        p.append(f'<circle class="d-num" cx="428" cy="{y + 42}" r="14"/>')
        p.append(txt(428, y + 46, str(i + 1), "d-numt", "middle"))
        p.append(txt(456, y + 30, name, "d-st"))
        p.append(txt(456, y + 52, l1, "d-ss"))
        p.append(txt(456, y + 70, l2, "d-ss"))
    p.append(txt(400, 500, "one schema &middot; one key &middot; two dates per row", "d-note"))
    p.append(txt(400, 524, "nothing hosted &middot; nothing redistributed &middot; 16 of 18 need no key", "d-fn"))

    # ---- wires in
    for i, group in enumerate(GROUP_ORDER):
        cy = group_mid[group]
        ty = 138 + i * 96
        d = f"M270 {cy:.0f} C322 {cy:.0f} 330 {ty} 380 {ty}"
        p.append(f'<path class="d-wire" d="{d}"/>')
        p.append(f'<path class="d-flow" style="animation-delay:{i * -0.4:.1f}s" d="{d}"/>')

    # ---- right: the six verbs, then the client
    p.append(card(830, 70, 310, 250, "d-box"))
    p.append(txt(850, 98, "SIX VERBS", "d-ct"))
    for i, v in enumerate(VERB_NAMES):
        cx, cy = 850 + (i % 2) * 146, 114 + (i // 2) * 54
        p.append(f'<rect class="d-verb" x="{cx}" y="{cy}" width="134" height="44" rx="9"/>')
        p.append(txt(cx + 67, cy + 27, v, "d-vt", "middle"))
    p.append(txt(850, 300, "source is a parameter, never a new tool", "d-fn"))

    p.append(card(830, 350, 310, 210, "d-box"))
    p.append(txt(850, 378, "YOUR AI CLIENT &middot; MCP", "d-ct"))
    p.append('<rect class="d-bub" x="850" y="394" width="270" height="52" rx="10"/>')
    p.append(txt(866, 416, "backtest 12-1 momentum on the", "d-it"))
    p.append(txt(866, 434, "dow 30 since 2010", "d-it"))
    p.append(txt(850, 476, "sharpe 2.14", "d-ok"))
    p.append(txt(850, 500, "deflated 0.09 after 41 tries", "d-bad"))
    p.append(txt(850, 526, "claude &middot; cursor &middot; chatgpt &middot; anything", "d-fn"))

    for d, delay in [("M760 200 L830 195", 0.0), ("M985 320 L985 350", -0.8)]:
        p.append(f'<path class="d-wire" d="{d}"/>')
        p.append(f'<path class="d-flow" style="animation-delay:{delay}s" d="{d}"/>')
    p.append('<path class="d-arrow" d="M978 344 L985 352 L992 344"/>')

    p.append("</svg>")
    return "\n      ".join(p)


# -------------------------------------------------- diagram 2: point-in-time

# (label, second line, x on the axis, percent of the sweep when the wall reaches it)
PIT_EVENTS = [
    ("10-K FY2019 &middot; assets $338.5B", "public 31 Oct 2019", 333, 21.0),
    ("10-Q Q1 2020", "public 29 Jan 2020", 493, 38.4),
    ("FY2019 restated &middot; $323.9B", "public 30 Oct 2020", 973, 90.5),
]

PIT_ROWS = [
    ("assets $338.5B", "filed 31 Oct 2019", 21.0, "ok"),
    ("Q1 2020 filed", "filed 29 Jan 2020", 38.4, "ok"),
    ("assets $323.9B &middot; restatement", "filed 30 Oct 2020, row 1 stays", 90.5, "warn"),
]

PIT_TICKS = [(120, "Jul 2019"), (440, "Jan 2020"), (760, "Jul 2020"), (1080, "Jan 2021")]
PIT_LOOP = 11.0


def diagram_pit() -> str:
    p: list[str] = []
    p.append('<svg class="dia" viewBox="0 0 1160 440" role="img" '
             'aria-label="An as-of wall sweeping a timeline, revealing filings only once they were public">')

    p.append('<defs><clipPath id="plot"><rect x="118" y="60" width="964" height="230"/></clipPath></defs>')
    p.append(txt(20, 40, "TIME &rarr;", "d-h"))
    p.append(txt(1082, 326, "the day you are pretending it is", "d-fn", "end"))

    # the future, shaded, riding along with the wall
    p.append('<g clip-path="url(#plot)"><g class="pit-wall">'
             '<rect class="d-future" x="140" y="60" width="960" height="230"/>'
             '<line class="d-wallline" x1="140" y1="60" x2="140" y2="282"/>'
             '</g></g>')
    p.append('<g class="pit-wall"><rect class="d-walltag" x="102" y="34" width="76" height="22" rx="6"/>'
             + txt(140, 49, "today", "d-walltxt", "middle") + "</g>")

    # the axis
    p.append('<line class="d-axis" x1="118" y1="282" x2="1082" y2="282"/>')
    for x, lab in PIT_TICKS:
        p.append(f'<line class="d-tick" x1="{x}" y1="278" x2="{x}" y2="290"/>')
        p.append(txt(x, 308, lab, "d-fn", "middle"))

    # the filings
    for i, (lab, sub, x, at) in enumerate(PIT_EVENTS):
        y = 100 if i == 1 else 170
        DIA_CSS.append(f".pe{i}{{animation:{reveal(f'pev{i}', at, PIT_LOOP)}}}")
        p.append(f'<g class="pe{i}">')
        p.append(f'<line class="d-stem" x1="{x}" y1="{y + 52}" x2="{x}" y2="278"/>')
        p.append(f'<circle class="d-evdot" cx="{x}" cy="282" r="5"/>')
        p.append(f'<rect class="d-ev" x="{x - 150}" y="{y}" width="300" height="52" rx="10"/>')
        p.append(txt(x, y + 22, lab, "d-evt", "middle"))
        p.append(txt(x, y + 40, sub, "d-fn", "middle"))
        p.append("</g>")

    # the gap between "true" and "public", drawn once
    p.append('<line class="d-lag" x1="245" y1="248" x2="333" y2="248"/>')
    p.append(txt(289, 240, "nobody knew yet", "d-lagt", "middle"))
    p.append(txt(245, 266, "period ends Sep 2019", "d-fn", "middle"))

    # the panel that grows behind the wall
    p.append(card(20, 330, 1120, 92, "d-box"))
    p.append(txt(40, 356, "WHAT YOUR BACKTEST IS ALLOWED TO SEE", "d-ct"))
    for i, (lab, sub, at, kind) in enumerate(PIT_ROWS):
        x = 40 + i * 372
        DIA_CSS.append(f".pr{i}{{animation:{reveal(f'prow{i}', at, PIT_LOOP, 0.0)}}}")
        p.append(f'<g class="pr{i}">')
        p.append(f'<rect class="d-row {kind}" x="{x}" y="368" width="336" height="38" rx="8"/>')
        p.append(txt(x + 14, 385, lab, "d-it"))
        p.append(txt(x + 14, 400, sub, "d-fn"))
        p.append("</g>")

    p.append("</svg>")
    return "\n      ".join(p)


# ------------------------------------------------------- diagram 3: honesty

HON_LOOP = 9.0
HON_SPECS = 41


def diagram_honesty() -> str:
    p: list[str] = []
    p.append('<svg class="dia" viewBox="0 0 1160 300" role="img" '
             'aria-label="41 specs feeding a trial ledger, collapsing a Sharpe of 2.14 to 0.09">')

    # ---- left: the specs you actually tried
    p.append(card(20, 50, 330, 210, "d-box"))
    p.append(txt(40, 78, "ONE RESEARCH SESSION", "d-ct"))
    for i in range(HON_SPECS):
        x, y = 40 + (i % 10) * 29, 110 + (i // 10) * 29
        at = 4 + i * 1.35
        DIA_CSS.append(f".sp{i}{{animation:{reveal(f'spec{i}', at, HON_LOOP, 0.08)}}}")
        p.append(f'<rect class="d-spec sp{i}" x="{x}" y="{y}" width="22" height="22" rx="4"/>')
    p.append(txt(40, 96, "41 ideas tried, every one counted", "d-fn"))

    # ---- middle: the ledger
    p.append(card(410, 80, 250, 150, "d-stage"))
    p.append(txt(430, 108, "TRIAL LEDGER", "d-ct"))
    p.append(txt(430, 150, "n = 41", "d-big"))
    p.append('<rect class="d-track" x="430" y="172" width="210" height="9" rx="5"/>')
    DIA_CSS.append(f".ledbar{{animation:{grow('ledgrow', 62, HON_LOOP, 210)}}}")
    p.append('<rect class="d-fill ledbar" x="430" y="172" height="9" rx="5"/>')
    p.append(txt(430, 206, "kept per session, automatically", "d-fn"))

    for d, delay in [("M350 155 L410 155", 0.0), ("M660 155 L720 155", -0.5)]:
        p.append(f'<path class="d-wire" d="{d}"/>')
        p.append(f'<path class="d-flow" style="animation-delay:{delay}s" d="{d}"/>')

    # ---- right: the deflation
    p.append(card(720, 50, 420, 210, "d-box"))
    p.append(txt(740, 78, "DEFLATED SHARPE &middot; BAILEY &amp; L&Oacute;PEZ DE PRADO (2014)", "d-ct"))

    p.append(txt(740, 122, "2.14", "d-big ok"))
    p.append('<rect class="d-track" x="812" y="110" width="308" height="12" rx="6"/>')
    p.append('<rect class="d-fill" x="812" y="110" width="287" height="12" rx="6"/>')
    p.append(txt(740, 142, "what your backtest reported", "d-fn"))

    p.append(txt(740, 186, "2.29", "d-mid"))
    p.append('<rect class="d-track" x="812" y="176" width="308" height="10" rx="5"/>')
    p.append('<rect class="d-fill amber" x="812" y="176" width="308" height="10" rx="5"/>')
    p.append(txt(740, 204, "what pure luck would have produced", "d-fn"))

    DIA_CSS.append(f".defbar{{animation:{grow('defgrow', 70, HON_LOOP, 12)}}}")
    DIA_CSS.append(f".defnum{{animation:{reveal('defnum', 70, HON_LOOP, 0.0)}}}")
    p.append('<g class="defnum">' + txt(740, 244, "0.09", "d-big bad") + "</g>")
    p.append('<rect class="d-track" x="812" y="234" width="308" height="12" rx="6"/>')
    p.append('<rect class="d-fill bad defbar" x="812" y="234" height="12" rx="6"/>')
    p.append('<g class="defnum">' + txt(880, 244, "what is left once the 41 tries are priced in", "d-fn") + "</g>")

    p.append("</svg>")
    return "\n      ".join(p)


# ------------------------------------------------------------ coverage bars

# (name, badge, coverage label, bar start %, bar end %), 1926 on the left.
SOURCES = [
    ("SEC EDGAR XBRL", "gov", "2009 → today", 83, 100),
    ("SEC filings stream", "gov", "1993 → today", 67, 100),
    ("FRED", "gov", "1947 → today", 21, 100),
    ("ALFRED vintages", "gov", "1996 → today", 70, 100),
    ("Ken French Library", "edu", "Jul 1926 → today", 0, 100),
    ("Open Source Asset Pricing", "edu", "1926 → 2023", 0, 97),
    ("FINRA short volume", "gov", "2009 → today", 83, 100),
    ("Coinbase Exchange", "third", "2015 → today", 89, 100),
    ("Yahoo Finance", "third", "1962 → today", 36, 100),
    ("ApeWisdom", "third", "live only, no history", 99, 100),
]


def build_timeline() -> str:
    return "\n        ".join(
        f'<div class="tl-row"><span class="tl-name">{name}</span>'
        f'<span class="tl-track"><i class="tl-bar {badge}" '
        f'style="left:{a}%;width:{max(b - a, 1.2):.1f}%"></i></span>'
        f'<span class="tl-span">{span}</span></div>'
        for name, badge, span, a, b in SOURCES
    )


DRIFT = [
    ("Lag", "true in December, published in February"),
    ("Restatement", "the company changes last year's number"),
    ("Revision", "the government keeps fixing old figures"),
    ("Survivorship", "dead companies quietly disappear"),
    ("Membership", "today's S&amp;P 500 is not 2005's list"),
    ("Adjustment", "splits rewrite every price before them"),
]


def build_drift() -> str:
    return "\n        ".join(
        f'<span class="drift"><b>{name}</b><i>{note}</i></span>' for name, note in DRIFT
    )


# ------------------------------------------------------------------ clients

CLIENTS = [
    (
        "Claude Code",
        "claude-code",
        "One command. Nothing to clone.",
        "claude mcp add vintage -s user -- uvx vintage-mcp",
    ),
    (
        "Claude Desktop",
        "claude-desktop",
        "Add to <code>claude_desktop_config.json</code>, then restart the app.",
        """{
  "mcpServers": {
    "vintage": {
      "command": "uvx",
      "args": ["vintage-mcp"]
    }
  }
}""",
    ),
    (
        "Cursor",
        "cursor",
        "Add to <code>~/.cursor/mcp.json</code>.",
        """{
  "mcpServers": {
    "vintage": {
      "command": "uvx",
      "args": ["vintage-mcp"]
    }
  }
}""",
    ),
    (
        "ChatGPT",
        "chatgpt",
        "Settings → Connectors → Developer mode. Needs a hosted URL, "
        "run <code>vintage</code> behind HTTPS and point the connector at it.",
        "uvx vintage-mcp --transport streamable-http --port 8000",
    ),
]


def build_forums() -> str:
    """What the forums are actually saying, fetched while the page is built.

    ApeWisdom publishes only the present. There is no history endpoint, and
    nobody can hand you last Tuesday's ranking. That is the honest demo: a live
    row, stamped with the minute we read it, and a note that the only way to own
    a history of this is to start recording it.
    """
    import datetime as _dt

    try:
        import httpx
        raw = httpx.get("https://apewisdom.io/api/v1.0/filter/all-stocks/page/1",
                        timeout=30).json()["results"][:8]
    except Exception:
        return ('<p class="after">The live forum panel could not be fetched when this '
                'page was built.</p>')

    rows = []
    for r in raw:
        now = int(r.get("mentions") or 0)
        before = int(r.get("mentions_24h_ago") or 0)
        delta = now - before
        cls = "up" if delta > 0 else ("down" if delta < 0 else "flat")
        arrow = "+" if delta > 0 else ""
        rows.append(
            f'<tr><td class="rk">{r.get("rank")}</td>'
            f'<td class="tk">{html.escape(html.unescape(str(r.get("ticker"))))}</td>'
            f'<td class="nm">{html.escape(html.unescape(str(r.get("name") or ""))[:26])}</td>'
            f'<td class="n">{now:,}</td>'
            f'<td class="n {cls}">{arrow}{delta:,}</td>'
            f'<td class="n dimc">{int(r.get("upvotes") or 0):,}</td></tr>')

    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        '<table class="forum"><thead><tr><th></th><th>ticker</th><th>name</th>'
        '<th class="n">mentions</th><th class="n">24h change</th>'
        '<th class="n">upvotes</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
        f'<p class="stamp">read from ApeWisdom at {stamp} &middot; '
        f'<code>known_at</code> is that moment, not the moment the posts were written</p>')


def build_clients() -> tuple[str, str]:
    tabs, panes = [], []
    for i, (label, slug, note, code) in enumerate(CLIENTS):
        active = " is-on" if i == 0 else ""
        tabs.append(f'<button class="tab{active}" data-pane="{slug}">{label}</button>')
        panes.append(
            f'<div class="pane{active}" id="{slug}">'
            f'<p class="note">{note}</p>'
            f'<pre><code>{html.escape(code)}</code>'
            f'<button class="copy" aria-label="Copy">copy</button></pre>'
            f"</div>"
        )
    return "\n          ".join(tabs), "\n        ".join(panes)


# --------------------------------------------------------------------- page

DEEP_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vintage, the long version</title>
<meta name="description" content="Vintage federates the free, point-in-time financial data of the web: eighteen primary sources (SEC EDGAR and Form 13F, FRED, US Treasury, BLS, BEA, ECB, CFTC, CBOE, Ken French and more) behind one interface and six verbs. You only ever see what was public that day. Sixteen of the eighteen need no key, and none of it costs anything.">

<meta property="og:type" content="website">
<meta property="og:title" content="Vintage, the free market research terminal">
<meta property="og:description" content="Vintage federates the free, point-in-time financial data of the web. Eighteen primary sources, one interface, six verbs, $0.">
<meta property="og:url" content="https://rezasoleymanifar.github.io/vintage/">
<meta property="og:image" content="https://rezasoleymanifar.github.io/vintage/og.png">
<meta name="twitter:card" content="summary_large_image">

<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%230b0f16'/><path d='M6 22 L13 12 L19 18 L26 8' stroke='%2335e08a' stroke-width='2.6' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>">

<style>
:root{
  --bg:#0b0f16; --panel:#0d1420; --line:#1f2b3a; --grid:#161f2c;
  --ink:#e8f1ec; --dim:#5f7a8c; --green:#35e08a; --red:#ff6b5e; --amber:#ffc46b;
  --blue:#7fb3ff;
  --mono:"IBM Plex Mono",ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font-family:var(--mono); font-size:16.8px; line-height:1.58;
  background-image:linear-gradient(var(--grid) 1px,transparent 1px);
  background-size:100% 60px;
}
.wrap{max-width:1060px;margin:0 auto;padding:0 20px}
a{color:var(--green);text-decoration:none}
a:hover{text-decoration:underline}

/* ------------------------------------------------------------------ hero */
header{padding:54px 0 8px}
.eyebrow{color:var(--dim);font-size:10.5px;letter-spacing:.24em;text-transform:uppercase;margin:0 0 16px}
h1{font-size:clamp(38px,8vw,74px);font-weight:700;letter-spacing:.16em;margin:0 0 10px;line-height:1}
.sub{
  color:var(--green);letter-spacing:.2em;font-size:clamp(11px,2.6vw,16px);margin:0;
  text-transform:uppercase;font-weight:700;
}
.claim{
  font-size:clamp(21px,4.2vw,33px);line-height:1.3;margin:30px 0 0;max-width:18em;font-weight:700;
}
.claim .g{color:var(--green)}
.gloss{
  margin:16px 0 0;padding:14px 16px;border-left:2px solid var(--green);
  background:linear-gradient(90deg,rgba(53,224,138,.06),transparent);
  font-size:clamp(14px,2.7vw,17px);line-height:1.55;max-width:34em;
}
.gloss b{color:var(--green)}
.pitch{font-size:clamp(13.5px,2.5vw,15.5px);line-height:1.6;margin:18px 0 0;max-width:36em;color:var(--dim)}
.pitch b{color:var(--ink);font-weight:700}

/* The architecture diagram is a wide SVG. On a phone it scrolls sideways
   rather than shrinking to unreadable, which is what the source labels need. */
.arch{margin:30px 0 0;padding:0;overflow-x:auto;-webkit-overflow-scrolling:touch}
.arch img{display:block;width:100%;min-width:820px;height:auto;
  border:1px solid var(--line);border-radius:10px;background:var(--bg)}
.arch figcaption{color:var(--dim);font-size:11px;letter-spacing:.06em;
  margin-top:10px;min-width:820px}
@media (max-width:700px){
  .arch img,.arch figcaption{min-width:760px}
}
.cta{margin:26px 0 0;display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center}
.ctanote{margin:0;color:var(--dim);font-size:12.5px}

.stats{
  display:grid;grid-template-columns:repeat(2,1fr);gap:1px;margin:30px 0 0;
  background:var(--line);border:1px solid var(--line);border-radius:11px;overflow:hidden;
}
@media(min-width:760px){.stats{grid-template-columns:repeat(6,1fr)}}
.stats div{background:var(--panel);padding:16px 12px;text-align:center}
.stats b{display:block;color:var(--green);font-size:clamp(20px,3.6vw,26px)}
.stats span{display:block;color:var(--dim);font-size:11px;letter-spacing:.06em;margin-top:5px;line-height:1.35}

/* ---------------------------------------------------------------- section */
section{padding:56px 0 0}
h2{font-size:clamp(19px,3.4vw,26px);color:var(--ink);margin:0 0 8px;font-weight:700}
.lede{color:var(--dim);font-size:14px;line-height:1.6;margin:0 0 20px;max-width:56em}
.lede .hl{color:var(--ink);font-weight:700}
.after{color:var(--dim);font-size:12.5px;margin:14px 0 0;line-height:1.6}

/* --------------------------------------------------------------- diagrams */
.dwrap{
  border:1px solid var(--line);border-radius:14px;background:var(--panel);
  padding:10px;overflow-x:auto;overflow-y:hidden;
}
.dwrap::-webkit-scrollbar{height:7px}
.dwrap::-webkit-scrollbar-thumb{background:var(--line);border-radius:4px}
.dia{display:block;width:100%;height:auto;min-width:940px}
.dia text{font-family:var(--mono)}
.d-orbring{fill:rgba(53,224,138,.07);stroke:var(--green);stroke-opacity:.32;stroke-width:1.1}
.d-orb{color:var(--green);animation:orb 4.6s ease-in-out infinite}
@keyframes orb{0%,100%{opacity:.6}50%{opacity:1}}
@media (prefers-reduced-motion:reduce){.d-orb{animation:none}}
.swipe{display:none;color:var(--dim);font-size:11px;margin:8px 0 0}
@media(max-width:980px){.swipe{display:block}}

.d-h{fill:var(--dim);font-size:11px;letter-spacing:.2em}
.d-h.g{fill:var(--green)}
.d-ct{fill:var(--dim);font-size:10.5px;letter-spacing:.18em}
.d-it{fill:var(--ink);font-size:12.5px}
.d-fn{fill:var(--dim);font-size:10.5px}
.d-note{fill:var(--green);font-size:11.5px}
.d-card{fill:rgba(255,255,255,.018);stroke:var(--line)}
.d-box{fill:#0a111a;stroke:var(--line)}
.d-edge{fill:var(--green);opacity:.55}
.d-pipe{fill:rgba(53,224,138,.05);stroke:rgba(53,224,138,.34)}
.d-stage{fill:#0a111a;stroke:var(--line)}
.d-num{fill:none;stroke:var(--green);stroke-width:1.3}
.d-numt{fill:var(--green);font-size:11.5px}
.d-st{fill:var(--green);font-size:14.5px;font-weight:700}
.d-ss{fill:var(--dim);font-size:11px}
.d-verb{fill:#0d1420;stroke:rgba(53,224,138,.32)}
.d-vt{fill:var(--green);font-size:12.5px}
.d-bub{fill:#0d1420;stroke:var(--line)}
.d-ok{fill:var(--green);font-size:13px;font-weight:700}
.d-bad{fill:var(--red);font-size:13px;font-weight:700}
.d-wire{stroke:#243447;stroke-width:1.6;fill:none}
.d-flow{stroke:var(--green);stroke-width:1.7;fill:none;stroke-dasharray:5 13;
  stroke-linecap:round;animation:flow 1.5s linear infinite}
@keyframes flow{to{stroke-dashoffset:-36}}
.d-arrow{fill:none;stroke:var(--green);stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}

.d-axis{stroke:var(--line);stroke-width:1.5}
.d-tick{stroke:var(--line);stroke-width:1.5}
.d-future{fill:rgba(255,107,94,.055)}
.d-wallline{stroke:var(--red);stroke-width:1.6;stroke-dasharray:5 5}
.d-walltag{fill:var(--red)}
.d-walltxt{fill:#0b0f16;font-size:11px;font-weight:700}
.d-ev{fill:#0a111a;stroke:rgba(53,224,138,.34)}
.d-evt{fill:var(--ink);font-size:12.5px;font-weight:700}
.d-evdot{fill:var(--green)}
.d-stem{stroke:#243447;stroke-width:1.3;stroke-dasharray:3 4}
.d-lag{stroke:var(--red);stroke-width:1.6;stroke-dasharray:4 4}
.d-lagt{fill:var(--red);font-size:10.5px}
.d-row{fill:#0d1420;stroke:var(--line)}
.d-row.warn{stroke:rgba(255,196,107,.5)}
.pit-wall{animation:sweep 11s linear infinite}
@keyframes sweep{to{transform:translateX(920px)}}

.d-spec{fill:var(--green);opacity:.9}
.d-track{fill:#101927}
.d-fill{fill:var(--green)}
.d-fill.amber{fill:var(--amber)}
.d-fill.bad{fill:var(--red)}
.d-big{font-size:26px;font-weight:700;fill:var(--ink)}
.d-big.ok{fill:var(--green)}
.d-big.bad{fill:var(--red)}
.d-mid{font-size:20px;font-weight:700;fill:var(--amber)}

@media (prefers-reduced-motion:reduce){
  .dia *{animation:none!important;transform:none!important;opacity:1!important}
  .d-future,.pit-wall{display:none}
  .defbar{width:12px}.ledbar{width:210px}
}

/* -------------------------------------------------------------- timeline */
.tl{margin-top:18px;border:1px solid var(--line);border-radius:12px;background:var(--panel);padding:18px 16px 14px}
.tl-head{display:flex;justify-content:space-between;color:var(--dim);font-size:10.5px;
  letter-spacing:.18em;text-transform:uppercase;margin-bottom:14px}
.tl-row{display:grid;grid-template-columns:1fr;gap:3px;margin-bottom:11px}
@media(min-width:700px){.tl-row{grid-template-columns:15em 1fr 9em;gap:12px;align-items:center;margin-bottom:7px}}
.tl-name{font-size:12.5px;color:var(--ink)}
.tl-track{position:relative;display:block;height:9px;border-radius:5px;background:#101927;overflow:hidden}
.tl-bar{position:absolute;top:0;height:9px;border-radius:5px;display:block}
.tl-bar.gov{background:var(--green)}
.tl-bar.edu{background:var(--blue)}
.tl-bar.third{background:#3b5468}
.tl-span{font-size:11px;color:var(--dim)}
@media(min-width:700px){.tl-span{text-align:right}}

/* --------------------------------------------------------------- terminal */
.term{
  margin:0; background:var(--panel); border:1px solid var(--line);
  border-radius:12px; overflow:hidden; box-shadow:0 22px 60px -30px rgba(53,224,138,.3);
}
.bar{display:flex;align-items:center;gap:8px;padding:11px 15px;
  border-bottom:1px solid var(--line);background:#0a111a}
.tdot{width:11px;height:11px;border-radius:50%;background:#22303f;opacity:1}
.bar .who{margin-left:8px;color:var(--dim);font-size:12.5px;letter-spacing:.1em}
.screen{padding:18px 18px 22px;font-size:clamp(11.5px,2.3vw,14.5px);min-height:330px}

.row{display:flex;align-items:baseline;flex-wrap:wrap;gap:0 8px;padding:1.5px 0;opacity:0}
.in1{padding-left:1.6em}
.prompt{font-weight:700}
.p-shell{color:var(--dim)}
.p-user{color:var(--green)}
.typed{display:inline-block;overflow:hidden;white-space:nowrap;vertical-align:bottom;width:0}
.caret{display:inline-block;width:.58em;height:1.05em;background:var(--green);
  vertical-align:text-bottom;visibility:hidden}
@keyframes blink{0%{opacity:1}50%{opacity:0}}

.dim{color:var(--dim)}
.ok{color:var(--green)}
.ok b{margin-right:7px}
.kv .k{color:var(--dim)}
.kv .v{color:var(--ink);font-weight:700;margin-right:20px}
.kv.big .v{color:var(--green);font-size:1.5em}
.kv.mid .v{color:var(--ink)}
.kv.bad .v{color:var(--red);font-size:1.25em}
.verdict{color:var(--red)}
.kicker{color:var(--amber)}
.rule{color:var(--dim);letter-spacing:.22em;font-size:.82em;margin-top:14px;
  text-transform:uppercase;gap:12px}
.rule i{flex:1;height:1px;background:var(--line);min-width:14px}

@media (prefers-reduced-motion:reduce){
  .row{opacity:1!important;animation:none!important;transform:none!important}
  .typed{width:auto!important;animation:none!important}
  .caret{display:none}
}

/* ------------------------------------------------------------- chip rows */
.drifts{display:grid;grid-template-columns:1fr;gap:9px;margin-top:16px}
@media(min-width:600px){.drifts{grid-template-columns:repeat(2,1fr)}}
@media(min-width:940px){.drifts{grid-template-columns:repeat(3,1fr)}}
.drift{display:block;border-left:2px solid var(--amber);padding:2px 0 2px 11px}
.drift b{display:block;font-size:12.5px}
.drift i{display:block;font-style:normal;color:var(--dim);font-size:11.5px;margin-top:1px}

.papers{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.paper{border:1px solid var(--line);border-radius:7px;padding:7px 11px;font-size:11.5px;color:var(--dim)}
.paper b{color:var(--ink);font-weight:700}
.paper.on{border-color:rgba(53,224,138,.4);background:rgba(53,224,138,.07)}
.paper.on b{color:var(--green)}
.paper.off b{color:var(--amber)}

/* --------------------------------------------------------------- install */
.tabs{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:14px}
.tab{font-family:var(--mono);font-size:13px;color:var(--dim);cursor:pointer;
  background:transparent;border:1px solid var(--line);border-radius:7px;padding:7px 13px}
.tab:hover{color:var(--ink)}
.tab.is-on{color:var(--bg);background:var(--green);border-color:var(--green);font-weight:700}
.pane{display:none}
.pane.is-on{display:block}
.note{color:var(--dim);font-size:14px;margin:0 0 11px}
.note code{color:var(--ink)}
pre{position:relative;margin:0;background:var(--panel);border:1px solid var(--line);
  border-radius:10px;padding:15px 74px 15px 16px;overflow-x:auto;
  font-size:13.5px;line-height:1.65;color:var(--green)}
pre.one{flex:1 1 30em;padding:14px 74px 14px 16px;font-size:clamp(11.5px,2.2vw,13.5px)}
.one{position:relative;animation:beckon 2.8s ease-in-out infinite}
@keyframes beckon{
  0%,100%{border-color:var(--line);box-shadow:0 0 0 0 rgba(53,224,138,0)}
  50%{border-color:var(--green);box-shadow:0 0 0 3px rgba(53,224,138,.13),
      0 0 26px rgba(53,224,138,.20)}}
.one code{color:var(--green)}
@media (prefers-reduced-motion:reduce){.one{animation:none;border-color:var(--green)}}
.copy{position:absolute;top:10px;right:10px;font-family:var(--mono);font-size:11.5px;
  letter-spacing:.1em;color:var(--dim);background:#0a111a;border:1px solid var(--line);
  border-radius:6px;padding:5px 10px;cursor:pointer}
.copy:hover{color:var(--green);border-color:var(--green)}
.copy.done{color:var(--bg);background:var(--green);border-color:var(--green)}

footer{padding:56px 0 70px;color:var(--dim);font-size:12.5px}
footer .links{display:flex;flex-wrap:wrap;gap:18px;margin-bottom:14px;font-size:13.5px}
__DIACSS__

.forum{width:100%;border-collapse:collapse;margin:22px 0 0;font-size:14px}
.forum th{color:var(--dim);font-size:11px;letter-spacing:.12em;text-transform:uppercase;
  font-weight:400;text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
.forum td{padding:10px;border-bottom:1px solid var(--line);color:var(--ink)}
.forum td.rk{color:var(--dim);width:2em}
.forum td.tk{font-weight:700;letter-spacing:.04em}
.forum td.nm{color:var(--dim)}
.forum .n{text-align:right;font-variant-numeric:tabular-nums}
.forum th.n{text-align:right}
.forum .up{color:var(--green)}
.forum .down{color:var(--red)}
.forum .flat,.forum .dimc{color:var(--dim)}
.stamp{color:var(--dim);font-size:12.5px;margin:12px 0 0}
</style>
</head>
<body>

<div class="wrap">

  <header>
    <p class="eyebrow">MCP server &middot; open source &middot; 16 of 18 sources need no key</p>
    <h1>VINTAGE</h1>
    <p class="sub">Free market research terminal</p>

    <p class="claim">Vintage <span class="g">federates the free, point-in-time financial data of
    the web</span>.</p>
    <p class="gloss"><b>Point-in-time</b> means you only ever see what the world could actually see
    that day. No number that was revised, restated or listed years later leaks backwards into a test
    of the past.</p>
    <p class="pitch">There is no free lunch in market data, the real terminals cost more than a car.
    But most of what they sell is <b>already public and already free</b>, just scattered across a
    dozen government, university and exchange sites in ten incompatible formats, none of them
    keeping track of when anything became known.
    <b>Vintage is the closest thing to a free terminal</b>: one pipeline, one schema, one interface.</p>

    <figure class="arch">
      <img src="architecture.svg" width="1280" height="880" alt="Eighteen free
      financial data sources: SEC EDGAR, Form 13F, FRED, ECB, US Treasury, BLS, BEA,
      CFTC, CBOE, FINRA, Coinbase, Ken French and more, federated behind one interface,
      every row carrying both the date it describes and the date it became public">
      <figcaption>Eighteen sources scattered across the internet, one interface,
      every value dated twice.</figcaption>
    </figure>

    <div class="cta">
      <pre class="one"><code>claude mcp add vintage -s user -- uvx vintage-mcp</code><button class="copy" aria-label="Copy">copy</button></pre>
      <p class="ctanote">Free forever &middot; no account &middot; a free key only for FRED and BEA</p>
    </div>

    <div class="stats">
      <div><b>$0</b><span>total cost</span></div>
      <div><b>100</b><span>years of history</span></div>
      <div><b>18</b><span>primary sources</span></div>
      <div><b>6</b><span>verbs, that's the API</span></div>
      <div><b>800k+</b><span>macro series</span></div>
      <div><b>331</b><span>published anomalies</span></div>
    </div>
  </header>

  <section>
    <h2>How the federation works</h2>
    <p class="lede">Filings from the regulator that receives them, macro from the central bank that
    publishes it, factors from the university that computes them, then four stages that make
    them one dataset. <span class="hl">Vintage hosts none of it.</span></p>
    <div class="dwrap">
      __DIA1__
    </div>
    <p class="swipe">&larr; swipe the diagram sideways</p>

    <div class="tl">
      <div class="tl-head"><span>1926</span><span>what that federation covers</span><span>today</span></div>
      __TIMELINE__
    </div>
    <p class="after"><a href="https://github.com/RezaSoleymanifar/vintage/blob/main/COVERAGE.md">The
    full field-by-field catalogue</a> is generated from the registry, so it cannot drift from the code.</p>
  </section>

  <section>
    <h2>Point-in-time, in one picture</h2>
    <p class="lede">Gluing ten APIs together is a weekend. Keeping them
    <span class="hl">honest about time</span> is the whole job. Watch the day-marker sweep forward:
    a fact only enters your backtest once it was genuinely public, and a correction adds a row
    instead of erasing one.</p>
    <div class="dwrap">
      __DIA2__
    </div>
    <p class="swipe">&larr; swipe the diagram sideways</p>
    <div class="drifts">
      __DRIFT__
    </div>
    <p class="after">Six ways yesterday's data quietly changed underneath you. Sources that cannot
    supply an honest <code>known_at</code> are flagged <code>UNKNOWN_VINTAGE</code> rather than given
    a made-up date.</p>
  </section>

  <section>
    <h2>And it counts how many times you asked</h2>
    <p class="lede">Free data plus a fast backtester is a machine for fooling yourself. Vintage keeps
    a ledger of every idea you tried this session and prices it into the result.</p>
    <div class="dwrap">
      __DIA3__
    </div>
    <p class="swipe">&larr; swipe the diagram sideways</p>
    <div class="papers">
      <span class="paper on"><b>shipped</b> · point-in-time panel</span>
      <span class="paper on"><b>shipped</b> · costs on turnover</span>
      <span class="paper on"><b>shipped</b> · deflated Sharpe</span>
      <span class="paper on"><b>shipped</b> · session trial ledger</span>
      <span class="paper off"><b>planned</b> · PBO via CSCV</span>
      <span class="paper off"><b>planned</b> · purged k-fold + embargo</span>
      <span class="paper off"><b>planned</b> · minimum backtest length</span>
      <span class="paper off"><b>planned</b> · Newey-West</span>
      <span class="paper off"><b>planned</b> · square-root impact</span>
    </div>
    <p class="after">Execution realism is a different problem, already solved by
    <a href="https://www.quantconnect.com/lean">LEAN</a> and
    <a href="https://nautilustrader.io/">Nautilus Trader</a>. Vintage runs before that, where most
    ideas should die. Citations are references, not endorsements; anything marked planned is not in
    the code yet, and the <code>backtest</code> response says so at runtime.</p>
  </section>

  <section>
    <h2>What it feels like</h2>
    <div class="term">
      <div class="bar">
        <span class="tdot"></span><span class="tdot"></span><span class="tdot"></span>
        <span class="who">claude, vintage</span>
      </div>
      <div class="screen">
        __ROWS__
      </div>
    </div>
    <p class="after">Four more questions answered end to end on the <a href="reel.html">demo reel</a>.</p>
  </section>

  <section>
    <h2>What the forums are saying, right now</h2>
    <p class="lede">Fetched while this page was built. ApeWisdom ranks mention counts across roughly
    fifteen stock and crypto subreddits, and it publishes <span class="hl">only the present</span>
. There is no history endpoint, and nobody can sell you last Tuesday's ranking honestly,
    because anyone claiming years of it re-scored old posts with today's model.</p>
    __FORUMS__
    <p class="after">This is why the row is stamped rather than dated. Backtestable history starts the
    day you begin recording, which is the only version that survives contact with a
    <code>known_at</code> index.</p>
  </section>

  <section>
    <h2>Install</h2>
    <div class="tabs">
      __TABS__
    </div>
    __PANES__
    <p class="after">Needs <a href="https://docs.astral.sh/uv/getting-started/installation/">uv</a>.
    Prefer pip? <code>pip install vintage-mcp</code>, then use <code>vintage</code> as the command.
    Sixteen of the eighteen sources need no key. FRED and BEA take a free one.</p>
  </section>

  <footer>
    <div class="links">
      <a href="https://github.com/RezaSoleymanifar/vintage">GitHub</a>
      <a href="https://pypi.org/project/vintage-mcp/">PyPI</a>
      <a href="https://github.com/RezaSoleymanifar/vintage/blob/main/COVERAGE.md">Full data catalogue</a>
      <a href="https://github.com/RezaSoleymanifar/vintage/blob/main/DATA_SOURCES.md">Data landscape</a>
      <a href="https://github.com/RezaSoleymanifar/vintage/blob/main/DESIGN.md">Design</a>
    </div>
    <p>MIT licensed. Vintage redistributes no data, SEC EDGAR, FRED, Yahoo Finance and the
    Ken French library each keep their own terms. Counts current as of August 2026.
    Nothing here is investment advice.</p>
  </footer>

</div>

<style>__ANIM__</style>

<script>
document.querySelectorAll('.tab').forEach(function (tab) {
  tab.addEventListener('click', function () {
    document.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('is-on'); });
    document.querySelectorAll('.pane').forEach(function (p) { p.classList.remove('is-on'); });
    tab.classList.add('is-on');
    document.getElementById(tab.dataset.pane).classList.add('is-on');
  });
});

document.querySelectorAll('.copy').forEach(function (btn) {
  btn.addEventListener('click', function () {
    var code = btn.parentElement.querySelector('code').innerText;
    navigator.clipboard.writeText(code).then(function () {
      btn.textContent = 'copied';
      btn.classList.add('done');
      setTimeout(function () { btn.textContent = 'copy'; btn.classList.remove('done'); }, 1600);
    });
  });
});
</script>
</body>
</html>
"""


# ------------------------------------------------- the experiment, for real

# Every number below came out of Vintage on 2026-08-06 and is reproducible with
# the commands shown. The old script used an invented 2.14 Sharpe collapsing to
# 0.09, which is a strange thing to fake on a site about not faking numbers.
EXPERIMENT_LOOP = 22.0

EXPERIMENT: list = [
    Typed(0.2, "claude mcp add vintage -s user -- uvx vintage-mcp",
          prompt="$", prompt_class="p-shell", typing=1.5),
    Out(2.1, "connected · sec · fred · dartmouth · openap · coinbase · finra", cls="ok"),

    Typed(3.0, "replicate jegadeesh-titman momentum on the dow since 2010", typing=1.8),
    Out(5.2, "openap:Mom12m, the paper claimed 1.31%/month, t = 3.74, sample 1964-1989",
        cls="dim", indent=1),
    Out(5.7, "reading 30 tickers, 4,113 sessions · panel indexed on known_at", cls="dim", indent=1),
    Out(6.3, cells=[("annual return", "12.1%"), ("volatility", "19.4%"), ("max drawdown", "−29.5%")]),
    Out(6.9, cells=[("sharpe", "0.688")], cls="big"),
    Out(7.5, "WBA excluded, no price history. it delisted.", cls="kicker", indent=1),

    Typed(8.6, "is it decaying?", typing=0.9),
    Out(10.1, cells=[("first half", "0.883"), ("second half", "0.566")], cls="mid"),

    Typed(11.2, "is it just market beta?", typing=1.1),
    Out(13.0, cells=[("correlation with Mkt-RF", "0.74"), ("beta", "0.81"), ("R²", "0.56")],
        indent=1),
    Out(13.6, cells=[("alpha", "2.31%/yr")], cls="mid", indent=1),
    Out(14.4, "mostly Mkt-RF, with something else on top.", cls="verdict", indent=1),

    Out(15.4, "honesty report", cls="rule"),
    Out(15.8, cells=[("specs tried this session", "1")], indent=1),
    Out(16.3, "one spec, so nothing to deflate yet. ask twelve more and watch it fall.",
        cls="kicker", indent=1),
]


def build_session(script: list, loop: float, prefix: str) -> tuple[str, str]:
    """The keyframe terminal, but reusable, `prefix` keeps two of them apart."""
    rows: list[str] = []
    css: list[str] = []
    typed_times = [e.at for e in script if isinstance(e, Typed)]

    def at(t: float) -> float:
        return max(0.0, min(100.0, t / loop * 100.0))

    for i, ev in enumerate(script):
        k = f"{prefix}{i}"
        if isinstance(ev, Typed):
            n = len(ev.text)
            nxt = next((t for t in typed_times if t > ev.at), loop - 0.4)
            css.append(f"@keyframes a{k}{{0%,{at(ev.at - 0.05):.3f}%{{opacity:0}}"
                       f"{at(ev.at):.3f}%,100%{{opacity:1}}}}")
            css.append(f"@keyframes w{k}{{0%,{at(ev.at):.3f}%{{width:0}}"
                       f"{at(ev.at + ev.typing):.3f}%,100%{{width:{n}ch}}}}")
            css.append(f"@keyframes c{k}{{0%,{at(ev.at - 0.05):.3f}%{{visibility:hidden}}"
                       f"{at(ev.at):.3f}%,{at(nxt - 0.15):.3f}%{{visibility:visible}}"
                       f"{at(nxt - 0.1):.3f}%,100%{{visibility:hidden}}}}")
            css.append(f".r{k}{{animation:a{k} {loop}s infinite}}")
            css.append(f".t{k}{{animation:w{k} {loop}s steps({n},end) infinite}}")
            css.append(f".k{k}{{animation:c{k} {loop}s infinite,blink .9s steps(2,end) infinite}}")
            rows.append(f'<div class="row r{k}">'
                        f'<span class="prompt {ev.prompt_class}">{ev.prompt}</span>'
                        f'<span class="typed t{k}">{html.escape(ev.text)}</span>'
                        f'<span class="caret k{k}"></span></div>')
        else:
            css.append(f"@keyframes a{k}{{0%,{at(ev.at - 0.05):.3f}%{{opacity:0;transform:translateY(3px)}}"
                       f"{at(ev.at + 0.18):.3f}%,100%{{opacity:1;transform:none}}}}")
            css.append(f".r{k}{{animation:a{k} {loop}s infinite}}")
            classes = " ".join(c for c in ["row", f"r{k}", ev.cls,
                                           f"in{ev.indent}" if ev.indent else ""] if c)
            if ev.cells:
                inner = "".join(f'<span class="k">{html.escape(a)}</span>'
                                f'<span class="v">{html.escape(b)}</span>' for a, b in ev.cells)
                rows.append(f'<div class="{classes} kv">{inner}</div>')
            elif ev.cls == "rule":
                rows.append(f'<div class="{classes}"><i></i>{html.escape(ev.text)}<i></i></div>')
            elif ev.cls == "ok":
                rows.append(f'<div class="{classes}"><b>✓</b>{html.escape(ev.text)}</div>')
            else:
                rows.append(f'<div class="{classes}">{html.escape(ev.text)}</div>')

    return ("\n        ").join(rows), ("\n").join(css)


# ------------------------------------------------- diagram: what you get

def diagram_coverage() -> str:
    """A century of coverage, and the six verbs that reach all of it."""
    p: list[str] = []
    p.append('<svg class="dia" viewBox="0 0 1160 600" role="img" '
             'aria-label="Coverage of each source from 1926 to today, and the six verbs">')

    p.append(txt(40, 40, "A CENTURY OF COVERAGE", "d-h g"))
    p.append(txt(300, 70, "1926", "d-fn"))
    p.append(txt(1000, 70, "today", "d-fn", "end"))
    p.append('<line class="d-axis" x1="300" y1="78" x2="1000" y2="78"/>')

    for i, (name, badge, span, a, b) in enumerate(SOURCES):
        y = 100 + i * 33
        p.append(txt(40, y + 11, name, "d-it"))
        p.append(f'<rect class="d-track" x="300" y="{y}" width="700" height="13" rx="6"/>')
        x = 300 + a / 100 * 700
        w = max((b - a) / 100 * 700, 9)
        p.append(f'<rect class="tlb {badge}" x="{x:.0f}" y="{y}" width="{w:.0f}" height="13" rx="6"/>')
        p.append(txt(1150, y + 11, span, "d-fn", "end"))

    p.append(txt(40, 470, "SIX VERBS REACH ALL OF IT", "d-h g"))
    for i, v in enumerate(VERB_NAMES):
        x = 40 + i * 184
        p.append(f'<rect class="d-verb" x="{x}" y="492" width="170" height="54" rx="10"/>')
        p.append(txt(x + 85, 524, v, "d-vt", "middle"))
    p.append(txt(40, 578, "source is a parameter, never a new tool, twenty more sources adds zero verbs",
                 "d-fn"))

    p.append("</svg>")
    return ("\n      ").join(p)


# --------------------------------------------------------------------- icons
# Drawn on one 24-unit grid, stroked in the current colour, so a glyph inherits
# whatever the surrounding text is doing. Words the reader has to parse are the
# expensive part of a landing page; these carry the same meaning for free.

GLYPHS = {
    "stack":    '<path d="M12 3 3 7.5 12 12l9-4.5Z"/><path d="M3 12.5 12 17l9-4.5"/>'
                '<path d="M3 17 12 21.5 21 17"/>',
    "clock":    '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5.4l3.4 2"/>',
    "prompt":   '<rect x="2.5" y="4.5" width="19" height="15" rx="2.5"/>'
                '<path d="M6.5 9.5 9.5 12l-3 2.5"/><path d="M12.5 15h5"/>',
    "zero":     '<circle cx="12" cy="12" r="8.5"/><path d="M8 18.5 16 5.5"/>',
    "series":   '<path d="M3 20V4"/><path d="M3 20h18"/>'
                '<path d="M6 15.5 10 10l3.5 3.5L20 6"/>',
    "flask":    '<path d="M9.5 3v6.2L4.7 17.4A2 2 0 0 0 6.4 20.5h11.2a2 2 0 0 0 1.7-3.1L14.5 9.2V3"/>'
                '<path d="M8.5 3h7"/><path d="M7.4 14h9.2"/>',
    "install":  '<path d="M12 3.5v11"/><path d="M8 11l4 3.5 4-3.5"/>'
                '<path d="M4.5 18.5h15"/>',
    "ask":      '<path d="M20.5 14.5a2 2 0 0 1-2 2H8l-4.5 4V5.5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2Z"/>'
                '<path d="M8 8.5h8"/><path d="M8 12h5"/>',
    "shield":   '<path d="M12 3 5 6v5.5c0 4.3 2.9 7.6 7 9.5 4.1-1.9 7-5.2 7-9.5V6Z"/>'
                '<path d="M9 12l2.2 2.2L15.5 10"/>',
    "scatter":  '<circle cx="5.5" cy="7" r="1.8"/><circle cx="12" cy="4.8" r="1.8"/>'
                '<circle cx="18.5" cy="8.5" r="1.8"/><circle cx="7" cy="16.5" r="1.8"/>'
                '<circle cx="16" cy="18" r="1.8"/><circle cx="11.5" cy="11.5" r="1.8"/>',
    "funnel":   '<path d="M3.5 4.5h17l-6.6 7.8v6.4l-3.8 2.3v-8.7Z"/>',
    "calendar": '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/>'
                '<path d="M3.5 10h17"/><path d="M8 3v4"/><path d="M16 3v4"/>'
                '<path d="M11 14.5h2"/>',
    "gov":      '<path d="M3.5 20.5h17"/><path d="M12 3 3.5 7.5h17Z"/>'
                '<path d="M6.5 10.5v7"/><path d="M11 10.5v7"/><path d="M15.5 10.5v7"/>'
                '<path d="M20 10.5v7"/>',
    "school":   '<path d="M12 3.5 2.5 8 12 12.5 21.5 8Z"/><path d="M6.5 10.2v5.3c0 1.9 2.5 3.2 5.5 3.2'
                's5.5-1.3 5.5-3.2v-5.3"/><path d="M21.5 8v5"/>',
    "wall":     '<path d="M12 3.5v17"/><path d="M4 7.5h5"/><path d="M4 12h5"/><path d="M4 16.5h5"/>'
                '<path d="M15.5 9.5h4.5"/><path d="M15.5 14.5h4.5"/>',
    "ledger":   '<rect x="4" y="3.5" width="16" height="17" rx="2.2"/><path d="M8 8h8"/>'
                '<path d="M8 12h8"/><path d="M8 16h4.5"/>',
    "fall":     '<path d="M3 5.5 12 14l3.5-3.5L21 16"/><path d="M21 11v5h-5"/>',
    "coin":     '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v10"/>'
                '<path d="M14.6 9.2A2.8 2.8 0 0 0 12 8c-1.7 0-2.8.9-2.8 2s1 1.8 2.8 2 2.8.8 2.8 2'
                '-1.1 2-2.8 2a2.8 2.8 0 0 1-2.6-1.2"/>',
}


def icon(name: str, size: int = 15) -> str:
    """One glyph, inheriting the colour and the line height around it."""
    return (f'<svg class="ic" viewBox="0 0 24 24" width="{size}" height="{size}" '
            f'fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{GLYPHS[name]}</svg>')


# The rail used to say all of this in sentences. Six numbers say it faster.
TILES = [
    ("stack", "18", "free sources"),
    ("clock", "100", "years deep"),
    ("prompt", "6", "verbs, whole API"),
    ("zero", "$0", "forever"),
    ("series", "800k", "macro series"),
    ("flask", "331", "published anomalies"),
]

STEPS = [
    ("install", "install", "one command"),
    ("ask", "ask", "plain English"),
    ("shield", "check", "honesty report"),
]

# One line of evidence per panel, in place of the paragraph that was there.
FACTS = {
    "__F1__": [("gov", "regulators and central banks"),
               ("school", "universities, not resellers"),
               ("funnel", "one schema out")],
    "__F2__": [("calendar", "July 1926 to this morning"),
               ("prompt", "a source is a parameter"),
               ("stack", "more sources, same six verbs")],
    "__F3__": [("wall", "nothing crosses the day marker"),
               ("calendar", "corrections add a row"),
               ("shield", "no honest date, no silent guess")],
    "__F5__": [("ledger", "it counts how many times you asked"),
               ("fall", "the Sharpe is deflated for that count"),
               ("shield", "published methods, cited on the page")],
    "__F4__": [("ledger", "41 specs counted this session"),
               ("fall", "Sharpe 2.14 deflates to 0.09"),
               ("prompt", "every number reproducible")],
}


def build_tiles() -> str:
    return "\n      ".join(
        f'<div class="tile">{icon(g, 16)}<b>{n}</b><span>{w}</span></div>'
        for g, n, w in TILES)


def build_steps() -> str:
    return "\n      ".join(
        f'<div class="step">{icon(g, 15)}<b>{n}</b><span>{w}</span></div>'
        for g, n, w in STEPS)


# The backtest-validation literature, named rather than paraphrased, with what
# is in the code separated from what is not. A terminal claim that cannot show
# its methods is a slogan.
METHODS = [
    ("on", "Point-in-time panel indexed on known_at", "structural, no flag disables it"),
    ("on", "Costs charged on turnover", "there is no zero-cost mode"),
    ("on", "Deflated Sharpe Ratio", "Bailey &amp; L&oacute;pez de Prado, 2014"),
    ("on", "Session trial ledger", "every spec you tried, priced into the result"),
    ("off", "Probability of Backtest Overfitting", "Bailey, Borwein, L&oacute;pez de Prado &amp; Zhu, 2017"),
    ("off", "Purged k-fold with embargo", "Advances in Financial Machine Learning, ch. 7"),
    ("off", "Minimum Backtest Length", "Bailey, Borwein, L&oacute;pez de Prado &amp; Zhu, 2014"),
    ("off", "Newey-West, square-root impact", "Newey &amp; West 1987; Almgren 2005"),
]


def build_methods() -> str:
    rows = "".join(
        f'<div class="method {state}"><b>{name}</b><span>{cite}</span></div>'
        for state, name, cite in METHODS)
    return (f'<div class="mhead"><span class="on">in the code</span>'
            f'<span class="off">named, not yet built</span></div>{rows}')


def build_facts(key: str) -> str:
    return ('<div class="facts">' + "".join(
        f'<span class="fact">{icon(g, 14)}{w}</span>' for g, w in FACTS[key]) + '</div>')


ONE_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vintage, the free market research terminal</title>
<meta name="description" content="Vintage federates the free, point-in-time financial data of the web. Eighteen sources, one interface, six verbs, $0.">
<meta property="og:type" content="website">
<meta property="og:title" content="Vintage, the free market research terminal">
<meta property="og:description" content="Vintage federates the free, point-in-time financial data of the web. Eighteen sources, one interface, six verbs, $0.">
<meta property="og:url" content="https://rezasoleymanifar.github.io/vintage/">
<meta property="og:image" content="https://rezasoleymanifar.github.io/vintage/og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%230b0f16'/><path d='M6 22 L13 12 L19 18 L26 8' stroke='%2335e08a' stroke-width='2.6' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>">
<style>
:root{
  --bg:#080b11; --panel:#0c121c; --line:#1c2735; --ink:#e9f1ee; --dim:#657f92;
  --green:#2fd587; --red:#ff6b5e; --amber:#f2c076; --blue:#7fb3ff;
  --mono:"IBM Plex Mono",ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
html,body{height:100%}
body{
  margin:0;background:var(--bg);color:var(--ink);font-family:var(--mono);overflow:hidden;
  background-image:radial-gradient(ellipse 90% 60% at 78% 0%,rgba(47,213,135,.07),transparent 70%);
}
a{color:var(--green);text-decoration:none}
a:hover{text-decoration:underline}

.shell{height:100dvh;display:grid;grid-template-columns:1fr}
@media(min-width:1040px) and (min-height:640px){
  .shell{grid-template-columns:minmax(360px,31%) 1fr}
}

/* ------------------------------------------------------------- left rail */
.rail{
  padding:clamp(20px,3.4vh,44px) clamp(20px,2.6vw,40px);
  display:flex;flex-direction:column;gap:clamp(12px,2.2vh,26px);
  border-right:1px solid var(--line);min-width:0;
}
.brand{font-size:clamp(26px,4.4vh,44px);font-weight:700;letter-spacing:.17em;margin:0;line-height:1}
.tag{color:var(--green);letter-spacing:.19em;text-transform:uppercase;font-weight:700;
  font-size:clamp(9px,1.35vh,12px);margin:6px 0 0}
.claim{font-size:clamp(14px,2.15vh,20px);line-height:1.4;margin:0;font-weight:700}
.claim .g{color:var(--green)}
.sub{color:var(--dim);font-size:clamp(11px,1.55vh,13.5px);line-height:1.55;margin:0}

/* six numbers where six sentences used to be */
.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);
  border:1px solid var(--line);border-radius:10px;overflow:hidden}
.tile{background:var(--panel);padding:clamp(8px,1.35vh,13px) 9px;display:grid;
  justify-items:center;gap:2px;text-align:center}
.tile .ic{color:var(--green);opacity:.85}
.tile b{color:var(--ink);font-size:clamp(13px,2vh,18px);line-height:1.1;font-weight:700}
.tile span{color:var(--dim);font-size:clamp(8.5px,1.15vh,10.5px);line-height:1.25;
  letter-spacing:.04em}

.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}
.step{display:grid;justify-items:center;gap:2px;text-align:center;
  font-size:clamp(9px,1.2vh,11px)}
.step .ic{color:var(--green);opacity:.8}
.step b{color:var(--ink);font-weight:700;letter-spacing:.03em}
.step span{color:var(--dim)}

/* one line of evidence per panel, icon first */
.facts{display:flex;flex-wrap:wrap;gap:7px 14px;margin:0 0 clamp(8px,1.3vh,14px)}
.fact{display:inline-flex;align-items:center;gap:6px;color:var(--dim);
  font-size:clamp(9.5px,1.32vh,12px);line-height:1.3}
.fact .ic{color:var(--green);opacity:.8;flex:none}

/* the engine panel: the diagram wide on top, the literature banded beneath */
.split{flex:1;min-height:0;display:grid;grid-template-rows:minmax(0,1fr) auto;
  gap:clamp(8px,1.3vh,16px)}
.splitdia{min-width:0;min-height:0;display:flex}
.splitdia .dia{flex:1;width:100%;height:100%}
.methods{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));
  gap:clamp(5px,.8vh,10px) clamp(10px,1.4vw,20px)}
.mhead{grid-column:1/-1;display:flex;gap:16px;font-family:var(--mono);
  letter-spacing:.11em;text-transform:uppercase;font-size:clamp(8px,1.05vh,9.5px)}
.mhead .on{color:var(--green)}
.mhead .off{color:var(--dim)}
.mhead span{display:inline-flex;align-items:center;gap:6px}
.mhead span::before{content:"";width:7px;height:7px;border-radius:50%;
  background:currentColor;opacity:.85}
.method{border-left:2px solid var(--line);padding:1px 0 1px 9px;min-width:0}
.method b{display:block;color:var(--ink);font-size:clamp(9.5px,1.32vh,12px);
  font-weight:700;line-height:1.25}
.method span{display:block;color:var(--dim);font-size:clamp(8px,1.1vh,10px);
  line-height:1.3}
.method.on{border-left-color:rgba(47,213,135,.7)}
.method.off b{color:var(--dim)}
.mnote{grid-column:1/-1;margin:0;color:var(--dim);font-size:clamp(9px,1.2vh,11px);
  line-height:1.45;padding-top:7px;border-top:1px solid var(--line)}

@media(max-width:1039px),(max-height:639px){
  .methods{grid-template-columns:repeat(2,minmax(0,1fr))}
}

.cmd{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:9px;
  padding:11px 13px 11px 13px;color:var(--green);line-height:1.6;
  font-size:clamp(9.5px,1.3vh,12.5px);word-break:break-word}
.cmd code{display:block;padding-right:56px}
.copy{position:absolute;top:7px;right:7px;font-family:var(--mono);font-size:10.5px;
  letter-spacing:.09em;color:var(--dim);background:#070b11;border:1px solid var(--line);
  border-radius:6px;padding:4px 9px;cursor:pointer}
.copy:hover{color:var(--green);border-color:var(--green)}
.copy.done{color:var(--bg);background:var(--green);border-color:var(--green)}
.rail .foot{margin-top:auto;display:flex;flex-wrap:wrap;gap:12px;font-size:11px;color:var(--dim)}

/* ----------------------------------------------------------------- stage */
.stage{position:relative;display:flex;flex-direction:column;min-width:0;min-height:0;
  padding:clamp(16px,2.6vh,30px) clamp(16px,2.2vw,34px)}
.chips{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:clamp(10px,1.6vh,18px);flex:none}
.chip{font-family:var(--mono);font-size:clamp(9px,1.28vh,11.5px);letter-spacing:.11em;
  text-transform:uppercase;color:var(--dim);background:transparent;cursor:pointer;
  border:1px solid var(--line);border-radius:99px;padding:6px 13px;position:relative;overflow:hidden}
.chip:hover{color:var(--ink)}
.chip.is-on{color:var(--ink);border-color:rgba(47,213,135,.5)}
.chip.is-on::after{content:"";position:absolute;left:0;bottom:0;height:2px;background:var(--green);
  width:100%;transform-origin:left;animation:tick var(--dwell,9s) linear forwards}
@keyframes tick{from{transform:scaleX(0)}to{transform:scaleX(1)}}

.panels{position:relative;flex:1;min-height:0}
.panel{position:absolute;inset:0;opacity:0;visibility:hidden;
  transition:opacity .45s ease;display:flex;flex-direction:column;min-height:0}
.panel.is-on{opacity:1;visibility:visible}
.ptitle{font-size:clamp(13px,1.95vh,18px);font-weight:700;margin:0 0 4px}
.pnote{color:var(--dim);font-size:clamp(10px,1.4vh,12.5px);line-height:1.5;
  margin:0 0 clamp(8px,1.3vh,14px);max-width:70em}
.pnote b{color:var(--ink)}
.dia{flex:1;min-height:0;width:100%;height:100%}
.dia text{font-family:var(--mono)}
.d-orbring{fill:rgba(53,224,138,.07);stroke:var(--green);stroke-opacity:.32;stroke-width:1.1}
.d-orb{color:var(--green);animation:orb 4.6s ease-in-out infinite}
@keyframes orb{0%,100%{opacity:.6}50%{opacity:1}}
@media (prefers-reduced-motion:reduce){.d-orb{animation:none}}

/* the terminal panel */
.term{flex:0 1 auto;min-height:0;max-height:100%;background:var(--panel);
  border:1px solid var(--line);border-radius:11px;
  overflow:hidden;display:flex;flex-direction:column;
  box-shadow:0 26px 70px -40px rgba(47,213,135,.4)}
.bar{display:flex;align-items:center;gap:7px;padding:9px 13px;border-bottom:1px solid var(--line);
  background:#070b11;flex:none}
.tdot{width:9px;height:9px;border-radius:50%;background:#1e2b3a;opacity:1}
.bar .who{margin-left:7px;color:var(--dim);font-size:11px;letter-spacing:.1em}
.screen{padding:clamp(12px,2vh,22px);font-size:clamp(9px,1.85vh,17px);
  flex:0 1 auto;min-height:0;overflow:hidden}
.row{display:flex;align-items:baseline;flex-wrap:wrap;gap:0 7px;padding:1px 0;opacity:0}
.in1{padding-left:1.5em}
.prompt{font-weight:700}
.p-shell{color:var(--dim)}
.p-user{color:var(--green)}
.typed{display:inline-block;overflow:hidden;white-space:nowrap;vertical-align:bottom;width:0}
.caret{display:inline-block;width:.55em;height:1em;background:var(--green);
  vertical-align:text-bottom;visibility:hidden}
@keyframes blink{0%{opacity:1}50%{opacity:0}}
.dim{color:var(--dim)}
.ok{color:var(--green)}
.ok b{margin-right:6px}
.kv .k{color:var(--dim)}
.kv .v{color:var(--ink);font-weight:700;margin-right:17px}
.kv.big .v{color:var(--green);font-size:1.45em}
.kv.mid .v{color:var(--ink)}
.verdict{color:var(--amber);font-weight:700}
.kicker{color:var(--dim)}
.rule{color:var(--dim);letter-spacing:.2em;font-size:.8em;margin-top:9px;
  text-transform:uppercase;gap:11px}
.rule i{flex:1;height:1px;background:var(--line);min-width:12px}

/* diagram vocabulary */
.d-h{fill:var(--dim);font-size:11px;letter-spacing:.2em}
.d-h.g{fill:var(--green)}
.d-ct{fill:var(--dim);font-size:10.5px;letter-spacing:.18em}
.d-it{fill:var(--ink);font-size:12.5px}
.d-fn{fill:var(--dim);font-size:10.5px}
.d-note{fill:var(--green);font-size:11.5px}
.d-card{fill:rgba(255,255,255,.018);stroke:var(--line)}
.d-box{fill:#070b11;stroke:var(--line)}
.d-edge{fill:var(--green);opacity:.55}
.d-pipe{fill:rgba(47,213,135,.05);stroke:rgba(47,213,135,.32)}
.d-stage{fill:#070b11;stroke:var(--line)}
.d-num{fill:none;stroke:var(--green);stroke-width:1.3}
.d-numt{fill:var(--green);font-size:11.5px}
.d-st{fill:var(--green);font-size:14.5px;font-weight:700}
.d-ss{fill:var(--dim);font-size:11px}
.d-verb{fill:#0c121c;stroke:rgba(47,213,135,.3)}
.d-vt{fill:var(--green);font-size:13px}
.d-bub{fill:#0c121c;stroke:var(--line)}
.d-ok{fill:var(--green);font-size:13px;font-weight:700}
.d-bad{fill:var(--red);font-size:13px;font-weight:700}
.d-wire{stroke:#21303f;stroke-width:1.6;fill:none}
.d-flow{stroke:var(--green);stroke-width:1.7;fill:none;stroke-dasharray:5 13;
  stroke-linecap:round;animation:flow 1.5s linear infinite}
@keyframes flow{to{stroke-dashoffset:-36}}
.d-arrow{fill:none;stroke:var(--green);stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.d-axis,.d-tick{stroke:var(--line);stroke-width:1.5}
.d-future{fill:rgba(255,107,94,.055)}
.d-wallline{stroke:var(--red);stroke-width:1.6;stroke-dasharray:5 5}
.d-walltag{fill:var(--red)}
.d-walltxt{fill:#080b11;font-size:11px;font-weight:700}
.d-ev{fill:#070b11;stroke:rgba(47,213,135,.34)}
.d-evt{fill:var(--ink);font-size:12.5px;font-weight:700}
.d-evdot{fill:var(--green)}
.d-stem{stroke:#21303f;stroke-width:1.3;stroke-dasharray:3 4}
.d-lag{stroke:var(--red);stroke-width:1.6;stroke-dasharray:4 4}
.d-lagt{fill:var(--red);font-size:10.5px}
.d-row{fill:#0c121c;stroke:var(--line)}
.d-row.warn{stroke:rgba(242,192,118,.5)}
.pit-wall{animation:sweep 11s linear infinite}
@keyframes sweep{to{transform:translateX(920px)}}
.d-track{fill:#0e1723}
.tlb.gov{fill:var(--green)}
.tlb.edu{fill:var(--blue)}
.tlb.third{fill:#38536a}

@media (prefers-reduced-motion:reduce){
  .dia *,.row,.typed,.chip.is-on::after{animation:none!important;opacity:1!important}
  .typed{width:auto!important}
  .caret{display:none}
  .d-future,.pit-wall{display:none}
}

/* a phone or a short window cannot be one screen, let those scroll */
@media(max-width:1039px),(max-height:639px){
  body{overflow:auto}
  .shell{height:auto}
  .rail{border-right:0;border-bottom:1px solid var(--line)}
  .stage{min-height:88vh}
  .panels{min-height:70vh}
}
__ONECSS__
</style>
</head>
<body>
<div class="shell">

  <aside class="rail">
    <div>
      <h1 class="brand">VINTAGE</h1>
      <p class="tag">Free market research terminal</p>
    </div>

    <p class="claim">Vintage <span class="g">federates the free, point-in-time financial data of
    the web</span>.</p>
    <p class="sub">You only ever see what was public on the day you are asking about.</p>

    <div class="tiles">
      __TILES__
    </div>

    <div class="cmd"><code>claude mcp add vintage -s user -- uvx vintage-mcp</code><button class="copy" aria-label="Copy">copy</button></div>

    <div class="steps">
      __STEPS__
    </div>

    <div class="foot">
      <a href="https://github.com/RezaSoleymanifar/vintage">GitHub</a>
      <a href="https://pypi.org/project/vintage-mcp/">PyPI</a>
      <a href="deep.html">The long version</a>
      <a href="reel.html">Demo reel</a>
      <span>MIT &middot; $0 &middot; 16 of 18 sources need no key</span>
    </div>
  </aside>

  <main class="stage">
    <div class="chips" id="chips"></div>
    <div class="panels" id="panels">

      <section class="panel is-on" data-dwell="10">
        <h2 class="ptitle">The good data is already free. It is just scattered.</h2>
        __F1__
        __DIA1__
      </section>

      <section class="panel" data-dwell="14">
        <h2 class="ptitle">And a backtester that argues with you.</h2>
        __F5__
        <div class="split">
          <div class="splitdia">__DIA4__</div>
          <div class="methods">
            __METHODS__
            <p class="mnote">Nothing to install past the one line on the left. The engine
            runs on the same six verbs, over the panel the federation already built.</p>
          </div>
        </div>
      </section>

      <section class="panel" data-dwell="10">
        <h2 class="ptitle">A century of history, and six verbs that reach all of it.</h2>
        __F2__
        __DIA2__
      </section>

      <section class="panel" data-dwell="12">
        <h2 class="ptitle">Point-in-time, in one picture.</h2>
        __F3__
        __DIA3__
      </section>

      <section class="panel" data-dwell="23">
        <h2 class="ptitle">Does Jegadeesh-Titman momentum still work?</h2>
        __F4__
        <div class="term">
          <div class="bar">
            <span class="tdot"></span><span class="tdot"></span><span class="tdot"></span>
            <span class="who">claude, vintage</span>
          </div>
          <div class="screen">
        __EXPROWS__
          </div>
        </div>
      </section>

    </div>
  </main>
</div>

<script>
(function () {
  var panels = Array.prototype.slice.call(document.querySelectorAll('.panel'));
  var chipbar = document.getElementById('chips');
  var titles = ['What it is', 'The engine', 'What you get', 'Point-in-time', 'The experiment'];
  var timer, at = 0;

  var chips = titles.map(function (t, i) {
    var b = document.createElement('button');
    b.className = 'chip';
    b.textContent = t;
    b.addEventListener('click', function () { show(i); });
    chipbar.appendChild(b);
    return b;
  });

  // Restart the panel's animations, so a diagram is never joined mid-sweep.
  function replay(panel) {
    var nodes = panel.querySelectorAll('.row, .typed, .caret, .d-flow, .pit-wall');
    Array.prototype.forEach.call(nodes, function (el) {
      var keep = el.style.animation;
      el.style.animation = 'none';
      void el.offsetWidth;
      el.style.animation = keep;
    });
  }

  function show(i) {
    at = i;
    panels.forEach(function (p, n) { p.classList.toggle('is-on', n === i); });
    var dwell = (parseFloat(panels[i].dataset.dwell) || 9) * 1000;
    chips.forEach(function (c) {
      c.classList.remove('is-on');
      c.style.removeProperty('--dwell');
    });
    chips[i].style.setProperty('--dwell', (dwell / 1000) + 's');
    chips[i].classList.add('is-on');
    replay(panels[i]);
    clearTimeout(timer);
    timer = setTimeout(function () { show((at + 1) % panels.length); }, dwell);
  }

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    chips[0].classList.add('is-on');
  } else {
    show(0);
  }
})();

document.querySelectorAll('.copy').forEach(function (btn) {
  btn.addEventListener('click', function () {
    navigator.clipboard.writeText(btn.parentElement.querySelector('code').innerText).then(function () {
      btn.textContent = 'copied';
      btn.classList.add('done');
      setTimeout(function () { btn.textContent = 'copy'; btn.classList.remove('done'); }, 1500);
    });
  });
});
</script>
</body>
</html>
"""


REEL_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vintage, demo reel</title>
<meta name="robots" content="noindex">
<style>
:root{
  --bg:#0b0f16; --panel:#0d1420; --line:#1f2b3a;
  --ink:#e8f1ec; --dim:#5f7a8c; --green:#35e08a; --red:#ff6b5e; --amber:#ffc46b;
  --mono:"IBM Plex Mono",ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--mono)}
.wrap{max-width:1060px;margin:0 auto;padding:34px 20px 60px}
a{color:var(--green);text-decoration:none}
h1{font-size:15px;letter-spacing:.2em;color:var(--dim);text-transform:uppercase;
  font-weight:400;margin:0 0 18px}
__REELCSS__
</style>
</head>
<body>
<div class="wrap">
  <h1>Vintage, demo reel &middot; <a href="./">back to the site</a></h1>
  <div class="reel">__REEL__</div>
</div>
</body>
</html>
"""


def main() -> None:
    rows, anim = build_terminal()
    exp_rows, exp_anim = build_session(EXPERIMENT, EXPERIMENT_LOOP, "x")
    tabs, panes = build_clients()

    # Diagrams are built before the pages are assembled: each one appends its own
    # keyframes to DIA_CSS as a side effect, so both pages need the same block.
    dia1, dia2, dia3 = diagram_federation(), diagram_pit(), diagram_honesty()
    cover = diagram_coverage()
    diacss = "\n".join(DIA_CSS)

    # index.html, one screen, never scrolls, panels advance on a timer.
    one = (
        ONE_PAGE.replace("__DIA1__", dia1)
        .replace("__DIA2__", cover)
        .replace("__DIA3__", dia2)
        .replace("__EXPROWS__", exp_rows)
        .replace("__DIA4__", dia3)
        .replace("__METHODS__", build_methods())
        .replace("__TILES__", build_tiles())
        .replace("__STEPS__", build_steps())
        .replace("__ONECSS__", diacss + "\n" + exp_anim)
    )
    for key in FACTS:
        one = one.replace(key, build_facts(key))

    # deep.html, the long scrolling argument, for people who want it.
    deep = (
        DEEP_PAGE.replace("__ROWS__", rows)
        .replace("__DIA1__", dia1)
        .replace("__DIA2__", dia2)
        .replace("__DIA3__", dia3)
        .replace("__DIACSS__", diacss)
        .replace("__FORUMS__", build_forums())
        .replace("__TIMELINE__", build_timeline())
        .replace("__DRIFT__", build_drift())
        .replace("__TABS__", tabs)
        .replace("__PANES__", panes)
        .replace("__ANIM__", anim)
    )

    reel_html, reel_css = showcase.build()
    reel = (
        REEL_PAGE.replace("__REEL__", reel_html)
        .replace("__REELCSS__", showcase.STYLE + "\n" + reel_css)
    )

    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
    os.makedirs(root, exist_ok=True)
    for name, body in (("index.html", one), ("deep.html", deep), ("reel.html", reel)):
        with open(os.path.join(root, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        print(f"wrote {os.path.join(root, name)} ({len(body):,} bytes)")


if __name__ == "__main__":
    main()
