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

import hashlib
import html
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import showcase
from vintage import registry  # noqa: E402
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
    ("scales",   "House STOCK Act", "member trades, dated",  "REGULATORS"),
    ("bank",     "Senate EFD",     "member trades, dated",   "REGULATORS"),

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

# The source count is read off the registry, never typed. Three places on this
# page used to carry it as a literal and they had drifted to three different
# numbers, all of them wrong. A number that describes the code belongs to the
# code.
SOURCE_COUNT = len(registry.SOURCES)
KEYLESS_COUNT = sum(1 for s in registry.SOURCES if not s["key_required"])
PREFIX_COUNT = len(registry.PREFIXES)

WORDS = {18: "eighteen", 19: "nineteen", 20: "twenty", 21: "twenty-one",
         22: "twenty-two", 23: "twenty-three", 24: "twenty-four"}


def source_word(n: int) -> str:
    return WORDS.get(n, str(n))


GROUP_ORDER = ["REGULATORS", "CENTRAL BANKS", "MARKETS", "ACADEMIA"]

# What each family is, in the six words a reader will actually spend attention on.
GROUP_GLOSS = {
    "REGULATORS":    "what filers are compelled to disclose",
    "CENTRAL BANKS": "what the state measures about itself",
    "MARKETS":       "what changed hands, and at what price",
    "ACADEMIA":      "what has been published, and claimed",
}

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


# The federation bar is drawn by both diagram 1 and diagram 2, at the same x and
# the same width, so the second panel opens on the object the first one ended on.
# That shared block is the whole reason the two read as one argument rather than
# two unrelated pictures.
COL_X = [20, 305, 590, 875]
COL_W = 265
BAR_X, BAR_W, BAR_H = 20, 1120, 92


def vintage_bar(p: list[str], y: int, *, lede: str) -> None:
    """Vintage itself: one block, four stages, identical on both panels."""
    p.append(f'<rect class="d-pipe" x="{BAR_X}" y="{y}" width="{BAR_W}" '
             f'height="{BAR_H}" rx="14"/>')
    p.append(txt(BAR_X + 18, y + 24, "VINTAGE &middot; THE FEDERATION LAYER", "d-h g"))
    p.append(txt(BAR_X + BAR_W - 18, y + 24, lede, "d-fn", "end"))
    for i, (name, sub) in enumerate(BAR_STAGES):
        cx = BAR_X + 18 + i * 274
        p.append(card(cx, y + 34, 262, 46, "d-stage"))
        p.append(f'<circle class="d-num" cx="{cx + 25}" cy="{y + 57}" r="11"/>')
        p.append(txt(cx + 25, y + 61, str(i + 1), "d-numt", "middle"))
        p.append(txt(cx + 44, y + 53, name, "d-sb"))
        p.append(txt(cx + 44, y + 69, sub, "d-fn"))


BAR_STAGES = [
    ("resolve",           "one entity key, every source"),
    ("normalize",         "one schema, one unit"),
    ("stamp vintage",     "observed_at + known_at"),
    ("index on known_at", "point-in-time by construction"),
]


def diagram_federation() -> str:
    """Eighteen sources as a grid, in four families, trickling into Vintage.

    The previous version put the sources in a narrow left rail and the pipeline
    beside them, which made eighteen sources look like a list of four. A grid is
    the honest shape for a breadth claim: you can count it.
    """
    p: list[str] = []
    p.append('<svg class="dia" viewBox="0 0 1160 600" role="img" '
             'aria-label="Eighteen free data sources in four families - regulators, '
             'central banks, markets and academia - all flowing down into Vintage, '
             'which resolves, normalizes, stamps and indexes them">')

    p.append(txt(1140, 30, "every one of them public, and free, right now", "d-fn", "end"))

    # ---- the grid: one column per family, one card per source
    for gi, group in enumerate(GROUP_ORDER):
        members = [u for u in UNIVERSE if u[3] == group]
        x = COL_X[gi]
        p.append(f'<rect class="d-fam" x="{x}" y="44" width="{COL_W}" height="402" rx="12"/>')
        p.append(txt(x + 14, 68, group, "d-ct"))
        p.append(txt(x + COL_W - 14, 68, f"{len(members)}", "d-cnt", "end"))
        p.append(txt(x + 14, 84, GROUP_GLOSS[group], "d-fn"))

        for j, (glyph, name, holds, _g) in enumerate(members):
            cy = 98 + j * 49
            p.append(card(x + 10, cy, COL_W - 20, 44, "d-src"))
            p.append(f'<g class="d-orb" transform="translate({x + 23},{cy + 14})" '
                     f'style="animation-delay:{(gi * 5 + j) * -0.37:.2f}s">'
                     f'{icon(glyph, 16)}</g>')
            p.append(txt(x + 48, cy + 19, name, "d-it"))
            p.append(txt(x + 48, cy + 34, holds, "d-fn"))

    # ---- four drops into the bar. Straight, and into the block as a whole:
    # no family owns a stage, so no wire may appear to point at one.
    for i in range(4):
        cx = COL_X[i] + COL_W // 2
        d = f"M{cx} 446 L{cx} 476"
        p.append(f'<path class="d-wire" d="{d}"/>')
        p.append(f'<path class="d-flow" style="animation-delay:{i * -0.4:.1f}s" d="{d}"/>')
        p.append(f'<path class="d-arrow" d="M{cx - 6} 468 L{cx} 476 L{cx + 6} 468"/>')

    vintage_bar(p, 476, lede="nothing hosted &middot; nothing redistributed &middot; "
                            "16 of the 18 need no key")

    p.append("</svg>")
    return "\n      ".join(p)


# ------------------------------------------------------ diagram 2: taxonomy

# Eighteen wire formats reduce to twenty-three prefixes, and the prefix is the
# whole addressing scheme: it is how `fetch` routes, how `discover` answers, and
# the reason a new source adds no new tool. Grouped the same four ways the source
# grid is grouped, so the eye carries the clustering across from the panel before.
#   family -> [(prefix, what it answers)]
TAXONOMY = [
    ("PRICES &amp; MARKETS", [
        ("price:",     "OHLCV, adjusted close"),
        ("index:",     "market indices"),
        ("crypto:",    "coin pairs, OHLCV"),
        ("fx:",        "euro reference rates"),
        ("vol:",       "VIX and the vol family"),
    ]),
    ("FILINGS", [
        ("us-gaap:",   "any tagged concept"),
        ("dei:",       "entity facts"),
        ("ifrs-full:", "foreign filers"),
        ("srt:",       "reporting taxonomy"),
        ("invest:",    "investment taxonomy"),
        ("filing:",    "8-K, 10-K, Form 4"),
        ("frame:",     "one concept, all filers"),
        ("13f:",       "institutional holdings"),
        ("congress:",  "House and Senate trades"),
        ("insider:",   "Form 4, with the code"),
        ("delisting:", "Form 25, every exit"),
    ]),
    ("MACRO &amp; RATES", [
        ("fred:",      "800k series, vintages"),
        ("bls:",       "CPI, payrolls, JOLTS"),
        ("bea:",       "the national accounts"),
        ("ust:",       "14-tenor yield curve"),
        ("cot:",       "weekly positioning"),
    ]),
    ("RESEARCH &amp; CROWD", [
        ("french:",    "Fama-French factors"),
        ("openap:",    "331 published claims"),
        ("short:",     "FINRA short volume"),
        ("ape:",       "forum mention ranks"),
    ]),
]


def diagram_taxonomy() -> str:
    """The same Vintage block, opened out into the field taxonomy it produces."""
    p: list[str] = []
    p.append('<svg class="dia" viewBox="0 0 1160 600" role="img" '
             'aria-label="Vintage distilling twenty-two sources into twenty-five field '
             'prefixes, grouped into prices, filings, macro and research, all reachable '
             'through the same six verbs">')

    # The panel opens on the block the previous panel closed on.
    # This used to read "the same block the last panel ended on", which was true
    # while the source grid was the slide before it. That slide is gone, so the
    # bar has to introduce itself instead of pointing back at nothing.
    vintage_bar(p, 16, lede=f"{source_word(SOURCE_COUNT)} sources in, one grammar out")

    p.append(txt(20, 132, "ONE TAXONOMY", "d-h g"))
    p.append(txt(1140, 132, f"{PREFIX_COUNT} PREFIXES", "d-h", "end"))

    for i in range(4):
        cx = COL_X[i] + COL_W // 2
        d = f"M{cx} 108 L{cx} 160"
        p.append(f'<path class="d-wire" d="{d}"/>')
        p.append(f'<path class="d-flow" style="animation-delay:{i * -0.4:.1f}s" d="{d}"/>')
        p.append(f'<path class="d-arrow" d="M{cx - 6} 152 L{cx} 160 L{cx + 6} 152"/>')

    for gi, (family, prefixes) in enumerate(TAXONOMY):
        x = COL_X[gi]
        p.append(f'<rect class="d-fam" x="{x}" y="160" width="{COL_W}" height="316" rx="12"/>')
        p.append(txt(x + 14, 184, family, "d-ct"))
        p.append(txt(x + COL_W - 14, 184, f"{len(prefixes)}", "d-cnt", "end"))
        for j, (prefix, answers) in enumerate(prefixes):
            y = 194 + j * 31
            p.append(f'<rect class="d-pill" x="{x + 10}" y="{y}" '
                     f'width="{COL_W - 20}" height="27" rx="7"/>')
            p.append(txt(x + 22, y + 18, prefix, "d-px"))
            p.append(txt(x + COL_W - 22, y + 18, answers, "d-ans", "end"))

    for i in range(4):
        cx = COL_X[i] + COL_W // 2
        d = f"M{cx} 476 L{cx} 500"
        p.append(f'<path class="d-wire" d="{d}"/>')
        p.append(f'<path class="d-flow" style="animation-delay:{i * -0.3:.1f}s" d="{d}"/>')

    for i, verb in enumerate(VERB_NAMES):
        x = 20 + i * 187
        p.append(f'<rect class="d-verb" x="{x}" y="500" width="175" height="52" rx="10"/>')
        p.append(txt(x + 87, 532, verb, "d-vt", "middle"))

    p.append(txt(20, 578, "six verbs reach every prefix &middot; source is a parameter, never a "
                          "new tool &middot; a bare field routes to EDGAR", "d-fn"))

    p.append("</svg>")
    return "\n      ".join(p)


# -------------------------------------------------------- diagram: the schema

# The claim the whole project rests on: the free financial web has no schema, and
# Vintage is one. Four publishers, four incompatible record shapes, none of them
# agreeing on what a date is called or whether the number has a unit. The fix is
# not a converter per pair; it is one row shape that all of them normalize into.
#   (publisher, wire format, [lines of the raw shape], what the shape is missing)
RAW_SHAPES = [
    ("SEC EDGAR", "XBRL JSON",
     ['"end":  …', '"val":  …', '"filed":  …', '"form":  …'],
     "two dates, both named something else"),
    ("FRED", "JSON",
     ['"date":  …', '"value":  …', '"realtime_start":  …', '"units":  …'],
     "the vintage lives in a third field"),
    ("Ken French", "fixed-width text",
     ['192607   …   …   …', '192608   …   …   …', '(no header row)', '(no units anywhere)'],
     "columns identified by position"),
    ("Coinbase", "JSON array",
     ['[ 1717200000,', '  low, high,', '  open, close,', '  volume ]'],
     "unnamed, and ordered by convention"),
]

# The nine keys of envelope.row(), in the order that function writes them.
SCHEMA_FIELDS = [
    ("entity",      "one key, resolved from ticker, CIK or name"),
    ("field",       "prefix:name, the same grammar for all 19"),
    ("observed_at", "the date the value describes"),
    ("known_at",    "the date it first became public"),
    ("value",       "the number itself"),
    ("unit",        "USD, percent, index level, ratio"),
    ("source",      "which publisher it came from"),
    ("source_url",  "the exact endpoint it was read from"),
    ("vintage",     "as-filed, or UNKNOWN_VINTAGE"),
]

# One real row, fetched from Vintage on 2026-08-06. Apple's FY2019 balance sheet,
# the period ending 28 Sep 2019, which the market could not see until 31 Oct.
SCHEMA_EXAMPLE = [
    ("entity", "CIK0000320193"),
    ("field", "us-gaap:Assets"),
    ("observed_at", "2019-09-28"),
    ("known_at", "2019-10-31"),
    ("value", "338516000000"),
    ("unit", "USD"),
]

SCHEMA_RULES = [
    ("Two dates, always",  "A row without an honest known_at is flagged "
                           "UNKNOWN_VINTAGE, never given a plausible date."),
    ("One key, so joins work", "Nine publishers, one entity key, so a join across "
                               "them is just a join."),
    ("One grammar, so tools don't grow", "A new source is a new prefix, not a new "
                                         "tool your agent has to learn."),
]


def diagram_schema() -> str:
    """Four incompatible wire formats, and the one row shape they all become."""
    p: list[str] = []
    p.append('<svg class="dia" viewBox="0 0 1160 600" role="img" '
             'aria-label="Four publishers with four incompatible record shapes, all '
             'normalized into one nine-field row carrying both the date it describes '
             'and the date it became public">')

    p.append(txt(20, 30, "24 PREFIXES, FOUR FAMILIES", "d-h"))
    p.append(txt(1140, 30, "AND ONE ROW SHAPE UNDER ALL OF THEM", "d-h g", "end"))

    for gi, (family, prefixes) in enumerate(TAXONOMY):
        x = COL_X[gi]
        p.append(f'<rect class="d-fam" x="{x}" y="44" width="{COL_W}" height="122" rx="12"/>')
        p.append(txt(x + 14, 66, family, "d-ct"))
        p.append(txt(x + COL_W - 14, 66, f"{len(prefixes)}", "d-cnt", "end"))
        shown = ", ".join(pref for pref, _ in prefixes[:4])
        rest = f" +{len(prefixes) - 4} more" if len(prefixes) > 4 else ""
        p.append(txt(x + 14, 92, shown, "d-px"))
        if rest:
            p.append(txt(x + 14, 112, rest.strip(), "d-fn"))
        p.append(txt(x + 14, 140, prefixes[0][1], "d-fn"))
        p.append(txt(x + 14, 156, "one grammar, any source", "d-fn"))

        cx = x + COL_W // 2
        d = f"M{cx} 166 L{cx} 196"
        p.append(f'<path class="d-wire" d="{d}"/>')
        p.append(f'<path class="d-flow" style="animation-delay:{gi * -0.4:.1f}s" d="{d}"/>')
        p.append(f'<path class="d-arrow" d="M{cx - 6} 188 L{cx} 196 L{cx + 6} 188"/>')

    p.append('<rect class="d-pipe" x="20" y="196" width="1120" height="238" rx="14"/>')
    p.append(txt(38, 222, "THE ROW EVERY SOURCE NORMALIZES TO", "d-h g"))
    p.append(txt(1122, 222, "nine fields, the same nine every time", "d-fn", "end"))

    for i, (name, meaning) in enumerate(SCHEMA_FIELDS):
        col, rw = i % 3, i // 3
        x, y = 38 + col * 366, 254 + rw * 46
        p.append(txt(x, y, name, "d-px"))
        p.append(txt(x, y + 15, meaning, "d-fn"))

    p.append('<rect class="d-bub" x="38" y="386" width="1084" height="34" rx="8"/>')
    step = 1084 // len(SCHEMA_EXAMPLE)
    for i, (key, val) in enumerate(SCHEMA_EXAMPLE):
        x = 50 + i * step
        p.append(txt(x, y_ex := 400, key, "d-exk"))
        p.append(txt(x, y_ex + 13, val, "d-exv"))

    for i, (head, body) in enumerate(SCHEMA_RULES):
        x = 20 + i * 380
        p.append(card(x, 456, 360, 92, "d-box"))
        p.append(txt(x + 16, 482, head, "d-sb"))
        words, line, lines = body.split(), "", []
        for w in words:
            if len(line) + len(w) + 1 > 44:
                lines.append(line)
                line = w
            else:
                line = f"{line} {w}".strip()
        lines.append(line)
        for j, ln in enumerate(lines[:3]):
            p.append(txt(x + 16, 504 + j * 15, ln, "d-fn"))

    p.append(txt(20, 578, "One real row, fetched on 2026-08-06: Apple's balance sheet closed "
                          "28 Sep 2019 and nobody could see it until 31 Oct.", "d-fn"))

    p.append("</svg>")
    return "\n      ".join(p)


# -------------------------------------------------- diagram 3: point-in-time

# The point-in-time idea told as a newsstand, because everyone already knows
# how a newspaper works: you can read the ones printed on or before today, the
# rest are not out yet, and a correction is a new edition rather than an edit
# to the paper already on the shelf.
#
# (masthead date, headline, second line, x of the paper, percent of the sweep)
PAPERS = [
    ("31 OCT 2019", "Assets $338.5B", "the annual report, as filed", 60, 7.6, False),
    ("29 JAN 2020", "Q1 comes in", "the quarter, as filed", 430, 47.8, False),
    ("30 OCT 2020", "Correction: $323.9B", "last year restated, a year later", 800, 88.0, True),
]

SLIPS = [
    ("assets $338.5B", "readable from 31 Oct 2019", 7.6, "ok"),
    ("Q1 2020 filed", "readable from 29 Jan 2020", 47.8, "ok"),
    ("assets $323.9B", "a second row. The first one still says $338.5B", 88.0, "warn"),
]

PIT_LOOP = 11.0


def diagram_pit() -> str:
    """A shelf of dated newspapers with today sweeping across it."""
    p: list[str] = []
    p.append('<svg class="dia" viewBox="0 0 1160 440" role="img" '
             'aria-label="A newsstand: today sweeps left to right, and a backtest may '
             'only read the papers already printed">')

    DIA_CSS.append(
        ".d-paper{fill:#101a26;stroke:rgba(53,224,138,.22)}"
        ".d-ghost{fill:none;stroke:rgba(53,224,138,.14);stroke-dasharray:5 5}"
        ".d-mast{fill:#5f7a8c;font-size:11px;letter-spacing:.2em}"
        ".d-head{fill:#e8f1ec;font-size:19px;font-weight:700}"
        ".d-head.warn{fill:var(--amber)}"
        ".d-col{stroke:#22323f;stroke-width:3;stroke-linecap:round}"
        ".d-shelf{stroke:rgba(53,224,138,.22);stroke-width:2}"
    )

    p.append(txt(20, 40, "THE NEWSSTAND", "d-h"))

    # today, sweeping. Everything to its right has not been printed yet.
    p.append('<g class="pit-wall">'
             '<rect class="d-future" x="140" y="56" width="1020" height="238"/>'
             '<line class="d-wallline" x1="140" y1="56" x2="140" y2="300"/></g>')
    p.append('<g class="pit-wall">'
             '<rect class="d-walltag" x="104" y="30" width="72" height="22" rx="6"/>'
             + txt(140, 45, "today", "d-walltxt", "middle") + "</g>")

    for i, (date, head, sub, x, at, warn) in enumerate(PAPERS):
        w, h, y = 300, 150, 76

        # what is on the shelf before it is printed
        p.append(f'<rect class="d-ghost" x="{x}" y="{y}" width="{w}" height="{h}" rx="8"/>')
        p.append(txt(x + w / 2, y + h / 2 + 5, "not printed yet", "d-fn", "middle"))

        DIA_CSS.append(f".pp{i}{{animation:{reveal(f'paper{i}', at, PIT_LOOP, 0.0)}}}")
        p.append(f'<g class="pp{i}">')
        p.append(f'<rect class="d-paper" x="{x}" y="{y}" width="{w}" height="{h}" rx="8"/>')
        p.append(txt(x + 18, y + 26, date, "d-mast"))
        p.append(f'<line class="d-shelf" x1="{x + 18}" y1="{y + 34}" x2="{x + w - 18}" y2="{y + 34}"/>')
        p.append(txt(x + 18, y + 62, head, "d-head warn" if warn else "d-head"))
        p.append(txt(x + 18, y + 82, sub, "d-fn"))
        for c in range(3):
            cx = x + 18 + c * 92
            for row in range(3):
                p.append(f'<line class="d-col" x1="{cx}" y1="{y + 104 + row * 13}" '
                         f'x2="{cx + 76}" y2="{y + 104 + row * 13}"/>')
        p.append("</g>")

    # the shelf itself
    p.append('<line class="d-shelf" x1="40" y1="240" x2="1120" y2="240"/>')
    p.append(txt(40, 262, "printed, dated, and never edited afterwards", "d-fn"))
    p.append(txt(1120, 262, "the day you are pretending it is", "d-fn", "end"))

    # what the backtest is handed
    p.append(card(20, 300, 1120, 120, "d-box"))
    p.append(txt(40, 328, "WHAT YOUR BACKTEST IS ALLOWED TO READ", "d-ct"))
    for i, (lab, sub, at, kind) in enumerate(SLIPS):
        x = 40 + i * 372
        DIA_CSS.append(f".pr{i}{{animation:{reveal(f'prow{i}', at, PIT_LOOP, 0.0)}}}")
        p.append(f'<g class="pr{i}">')
        p.append(f'<rect class="d-row {kind}" x="{x}" y="344" width="336" height="52" rx="8"/>')
        p.append(txt(x + 16, 368, lab, "d-it"))
        p.append(txt(x + 16, 386, sub, "d-fn"))
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


def build_timeline() -> str:
    """Every source as a banner with its span in words, matching the landing page.

    This was a bar chart against a 1926-to-today axis. The bar encoded one number
    as a length the reader then had to decode back into the year already printed
    at the end of the row, so it was ink spent to say a thing twice.
    """
    return "\n        ".join(
        f'<div class="tl-row {badge}"><span class="tl-name">{name}</span>'
        f'<span class="tl-badge {badge}">{BADGE_WORD[badge]}</span>'
        f'<span class="tl-span">{span}</span></div>'
        for name, badge, span in COVERAGE_BANNERS
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


# ----------------------------------------------------- installing it, played

# The two clients that work today, each as a short loop.

INSTALL_LOOP = 15.0

INSTALL_CODE: list = [
    Typed(0.2, "claude mcp add vintage -s user -- uvx vintage-mcp",
          prompt="$", prompt_class="p-shell", typing=2.8),
    Out(3.7, "resolving vintage-mcp from PyPI", cls="dim"),
    Out(4.7, "installed in 4.1s, nothing cloned", cls="dim"),
    Out(6.0, "vintage connected", cls="ok"),
    Out(7.0, cells=[("tools", "6"), ("sources", "18"), ("keys needed", "0")]),
    Typed(8.8, "what were Apple's total assets in Jan 2020?", typing=2.6),
    Out(12.2, "reading us-gaap:Assets as of 2020-01-01", cls="dim"),
    Out(13.2, "$338.5B, filed 31 Oct 2019", cls="ok"),
]

INSTALL_DESKTOP: list = [
    Out(0.1, "claude_desktop_config.json", cls="dim"),
    Typed(0.5, '{ "mcpServers": { "vintage": {', prompt="", prompt_class="p-shell",
          typing=1.7),
    Typed(3.0, '    "command": "uvx", "args": ["vintage-mcp"] } } }', prompt="",
          prompt_class="p-shell", typing=2.2),
    Out(5.8, "saved", cls="dim"),
    Out(6.8, "quit and reopen Claude Desktop", cls="dim"),
    Out(8.6, "vintage connected", cls="ok"),
    Out(9.6, cells=[("tools", "6"), ("sources", "18"), ("keys needed", "0")]),
    Out(11.4, "the hammer icon in the composer now lists six verbs", cls="dim"),
]

def build_install_reels() -> tuple[str, str]:
    """Two playing terminals and one honest card, for the install section."""
    code_rows, code_css = build_session(INSTALL_CODE, INSTALL_LOOP, "ic")
    desk_rows, desk_css = build_session(INSTALL_DESKTOP, INSTALL_LOOP, "id")

    def term(title: str, rows: str) -> str:
        return (f'<div class="reel"><div class="term">'
                f'<div class="bar"><span class="tdot"></span><span class="tdot"></span>'
                f'<span class="tdot"></span><span class="who">{title}</span></div>'
                f'<div class="screen">{rows}</div></div></div>')

    html_out = (f'<div class="reels">{term("claude code", code_rows)}'
                f'{term("claude desktop &middot; config", desk_rows)}</div>')
    return html_out, code_css + "\n" + desk_css


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
  --sans:"Segoe UI Variable Display","Segoe UI",Inter,"Helvetica Neue",ui-sans-serif,system-ui,sans-serif;
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
.d-card{fill:rgba(255,255,255,.018);stroke:rgba(53,224,138,.22)}
.d-box{fill:#0a111a;stroke:rgba(53,224,138,.22)}
.d-fam{fill:rgba(255,255,255,.012);stroke:rgba(53,224,138,.22)}
.d-src{fill:#0a111a;stroke:var(--line)}
.d-cnt{fill:var(--green);font-size:13px;font-weight:700}
.d-sb{fill:var(--green);font-size:13px;font-weight:700}
.d-raw{fill:var(--dim);font-size:10px}
.d-miss{fill:var(--red);font-size:10px}
.d-exk{fill:var(--dim);font-size:9.5px;letter-spacing:.1em}
.d-exv{fill:var(--green);font-size:11.5px;font-weight:700}
.d-pill{fill:#0d1420;stroke:rgba(53,224,138,.22)}
.d-ban{fill:#0a111a;stroke:var(--line)}
.d-edgemark{opacity:.85}
.d-edgemark.gov{fill:var(--green)}
.d-edgemark.edu{fill:#2fd587}
.d-edgemark.third{fill:#3b5468}
.d-bdg{font-size:10px;letter-spacing:.16em}
.d-rank{fill:var(--dim);font-size:10px;letter-spacing:.08em}
.d-yrs{fill:var(--ink);font-size:12px;font-weight:700}
.d-bdg.gov{fill:var(--green)}
.d-bdg.edu{fill:#2fd587}
.d-bdg.third{fill:#6b8299}
.d-px{fill:var(--green);font-size:12px;font-weight:700}
.d-ans{fill:var(--dim);font-size:10.5px}
.d-edge{fill:var(--green);opacity:.55}
.d-pipe{fill:rgba(53,224,138,.05);stroke:rgba(53,224,138,.34)}
.d-stage{fill:#0a111a;stroke:rgba(53,224,138,.22)}
.d-num{fill:none;stroke:var(--green);stroke-width:1.3}
.d-numt{fill:var(--green);font-size:11.5px}
.d-st{fill:var(--green);font-size:14.5px;font-weight:700}
.d-ss{fill:var(--dim);font-size:11px}
.d-verb{fill:#0d1420;stroke:rgba(53,224,138,.32)}
.d-vt{fill:var(--green);font-size:12.5px}
.d-bub{fill:#0d1420;stroke:rgba(53,224,138,.22)}
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
.d-row{fill:#0d1420;stroke:rgba(53,224,138,.22)}
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
.tl-row{display:grid;grid-template-columns:1fr;gap:3px;margin-bottom:9px;
  background:#0a111a;border:1px solid var(--line);border-left:3px solid var(--line);
  border-radius:8px;padding:7px 12px}
.tl-row.gov{border-left-color:var(--green)}
.tl-row.edu{border-left-color:#2fd587}
.tl-row.third{border-left-color:#3b5468}
@media(min-width:700px){.tl-row{grid-template-columns:16em 8em 1fr;gap:12px;align-items:center;margin-bottom:6px}}
.tl-name{font-size:12.5px;color:var(--ink)}
.tl-badge{font-size:10px;letter-spacing:.16em}
.tl-badge.gov{color:var(--green)}
.tl-badge.edu{color:#2fd587}
.tl-badge.third{color:#6b8299}
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
.drift{display:block;border-left:2px solid var(--green);padding:2px 0 2px 11px}
.drift b{display:block;font-size:12.5px}
.drift i{display:block;font-style:normal;color:var(--dim);font-size:11.5px;margin-top:1px}

.papers{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.paper{border:1px solid var(--line);border-radius:7px;padding:7px 11px;font-size:11.5px;color:var(--dim)}
.paper b{color:var(--ink);font-weight:700}
.paper.on{border-color:rgba(53,224,138,.4);background:rgba(53,224,138,.07)}
.paper.on b{color:var(--green)}
.paper.off b{color:var(--amber)}

/* --------------------------------------------------------------- install */
/* the install reels: two clients playing, one card explaining the third */
.reels{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:0 0 26px}
.reels .term{height:100%}
.reels .screen{font-size:12px;padding:16px 18px;min-height:236px;overflow:hidden}
.reel{min-width:0}
.reel .row{padding:1.5px 0}
.reel .kv .v{margin-right:11px}
.reel .kv .k{margin-right:3px}
@media(max-width:960px){.reels{grid-template-columns:1fr}}

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
      <div><b>22</b><span>primary sources</span></div>
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
      <div class="tl-head"><span>what that federation covers</span><span>standing</span><span>measured span</span></div>
      __TIMELINE__
    </div>
    <p class="after"><a href="https://github.com/RezaSoleymanifar/vintage/blob/main/COVERAGE.md">The
    full field-by-field catalogue</a> is generated from the registry, so it cannot drift from the code.</p>
  </section>

  <section>
    <h2>Point-in-time, in one picture</h2>
    <p class="lede">Gluing ten APIs together is a weekend. Keeping them
    <span class="hl">honest about time</span> is the whole job. Think of a newsstand: you may read
    the papers already printed and not tomorrow's, and a correction arrives as a new edition while
    the old paper stays on the shelf saying what it said.</p>
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
      <span class="paper on"><b>shipped</b> · PBO via CSCV</span>
      <span class="paper on"><b>shipped</b> · purged k-fold + embargo</span>
      <span class="paper on"><b>shipped</b> · combinatorial purged CV</span>
      <span class="paper on"><b>shipped</b> · minimum backtest length</span>
      <span class="paper on"><b>shipped</b> · Newey-West</span>
      <span class="paper on"><b>shipped</b> · square-root impact</span>
    </div>
    <p class="after">Execution realism is a different problem, already solved by
    <a href="https://www.quantconnect.com/lean">LEAN</a> and
    <a href="https://nautilustrader.io/">Nautilus Trader</a>. Vintage runs before that, where most
    ideas should die. Citations are references, not endorsements; every method above is in the
    code, and the <code>backtest</code> response carries each one at runtime.</p>
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
    <p class="lede">One line in Claude Code, or four in a config file for Claude Desktop.
    <span class="hl">Nothing to clone and no key to fetch first.</span></p>
    __INSTALLREEL__
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
EXPERIMENT_LOOP = 27.0

# One paper, taken all the way: claim, specification, implementation, backtest,
# and the honesty report at the end. Every number came out of Vintage on
# 2026-08-06 and is reproducible with the commands shown. The old script used an
# invented 2.14 Sharpe collapsing to 0.09, which is a strange thing to fake on a
# site about not faking numbers.
#
# The paper itself is picked from Alpha Archive, the companion project that reads
# papers and records which ones free data can actually reproduce. That is a
# separate repository, not a wired Vintage source, and the line below says so
# rather than implying an integration that does not exist yet.
EXPERIMENT: list = [
    Typed(0.2, "claude mcp add vintage -s user -- uvx vintage-mcp",
          prompt="$", prompt_class="p-shell", typing=1.5),
    Out(2.1, "connected · sec · fred · dartmouth · openap · coinbase · finra", cls="ok"),

    Typed(3.0, "take Jegadeesh-Titman (1993) and replicate it end to end", typing=1.9),

    Out(5.3, "the claim", cls="rule"),
    Out(5.7, "openap:Mom12m · Returns to Buying Winners and Selling Losers",
        cls="dim", indent=1),
    Out(6.2, cells=[("paper claimed", "1.31%/mo"), ("t-stat", "3.74"), ("sample", "1964-1989")],
        indent=1),

    Out(7.2, "the implementation", cls="rule"),
    Out(7.6, "rank on 12-1 total return · hold one month · long the top fifth",
        cls="dim", indent=1),
    Out(8.1, "resolve → 30 tickers · fetch → 4,113 sessions · panel indexed on known_at",
        cls="dim", indent=1),
    Out(8.6, "WBA excluded, no price history. it delisted. that is survivorship, in miniature.",
        cls="kicker", indent=1),

    Out(9.7, "the backtest · dow 30 since 2010", cls="rule"),
    Out(10.1, cells=[("annual return", "12.1%"), ("volatility", "19.4%"),
                     ("max drawdown", "−29.5%")]),
    Out(10.7, cells=[("sharpe", "0.688")], cls="big"),

    Typed(11.8, "is it decaying?", typing=0.9),
    Out(13.4, cells=[("first half", "0.883"), ("second half", "0.566")], cls="mid"),

    Typed(14.5, "is it just market beta?", typing=1.1),
    Out(16.3, cells=[("correlation with Mkt-RF", "0.74"), ("beta", "0.81"), ("R²", "0.56")],
        indent=1),
    Out(16.9, cells=[("alpha", "2.31%/yr")], cls="mid", indent=1),
    Out(17.7, "mostly Mkt-RF, with something else on top.", cls="verdict", indent=1),

    Out(18.8, "the honesty report", cls="rule"),
    Out(19.2, cells=[("specs tried this session", "1")], indent=1),
    Out(19.7, "one spec, so nothing to deflate yet. ask twelve more and watch it fall.",
        cls="kicker", indent=1),

    Out(20.9, "claim → spec → implementation → backtest → honesty. one prompt, no downloads.",
        cls="verdict"),
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

# The five numbers, then every source as a banner with its span in words.
# This was a bar chart against a 1926-to-today axis, which spent most of its ink
# encoding one number per row as a length the reader then had to decode back into
# a year. The year was already written at the end of the row. Only the years are
# kept, and the reader is trusted to know that 1926 is before 1962.
COVERAGE_STATS = [
    ("100",     "years, Jul 1926 on"),
    (str(SOURCE_COUNT), "primary sources"),
    (str(PREFIX_COUNT), "field prefixes"),
    ("331",     "published claims"),
    ("800k+",   "macro series"),
]

# (name, standing badge, the span, in words). Every span here is either measured
# from the source or quoted from its own documentation. Nothing is estimated: a
# source whose start date Vintage cannot establish says what it does instead.
COVERAGE_BANNERS = [
    # (name, standing, span in words, first year on record or None)
    # Ranked by depth of history, deepest first, because that is the question a
    # backtest actually asks of a source. Every year here is either measured from
    # the source or quoted from its own documentation; the four with no year are
    # cross-sections or live feeds, where a start date is not the right measure,
    # and they sort to the bottom rather than being given an invented one.
    ("Ken French Library",  "edu",   "Jul 1926 &rarr; today", 1926),
    ("Open Source AP",      "edu",   "1926 &rarr; 2023", 1926),
    ("FRED",                "gov",   "1947 &rarr; today", 1947),
    ("Yahoo Finance",       "third", "1962 &rarr; today", 1962),
    ("US Treasury",         "gov",   "1990 &rarr; today", 1990),
    ("CBOE volatility",     "gov",   "1990 &rarr; today", 1990),
    ("SEC filings stream",  "gov",   "1993 &rarr; today", 1993),
    ("ALFRED vintages",     "gov",   "1996 &rarr; today", 1996),
    ("ECB reference rates", "gov",   "1999 &rarr; today", 1999),
    ("SEC Form 25",         "gov",   "2003 &rarr; today", 2003),
    ("SEC EDGAR XBRL",      "gov",   "2009 &rarr; today", 2009),
    ("FINRA short volume",  "gov",   "2009 &rarr; today", 2009),
    ("Coinbase Exchange",   "third", "2015 &rarr; today", 2015),
    ("CFTC positioning",    "gov",   "2016 &rarr; today", 2016),
    ("House STOCK Act",     "gov",   "2008 &rarr; today", 2008),
    ("Senate EFD",          "gov",   "2012 &rarr; today", 2012),
    ("SEC Form 4 insiders",  "gov",   "2003 &rarr; today", 2003),
    ("BLS",                 "gov",   "2024 &rarr; today, keyless", 2024),
    ("SEC Form 13F",        "gov",   "by quarter, filed 45 days late", None),
    ("SEC XBRL frames",     "gov",   "any quarter, all filers at once", None),
    ("BEA",                 "gov",   "the current estimate only", None),
    ("ApeWisdom",           "third", "live only, no history", None),
]

THIS_YEAR = 2026

BADGE_WORD = {"gov": "PRIMARY", "edu": "ACADEMIC", "third": "THIRD PARTY"}


def diagram_coverage() -> str:
    """A century of coverage, said in words and banners rather than bars."""
    p: list[str] = []
    p.append('<svg class="dia" viewBox="0 0 1160 600" role="img" '
             'aria-label="A hundred years of coverage across every wired dataset, each '
             'with the years it spans and whether it comes from the primary publisher">')

    p.append(txt(20, 30, "A CENTURY OF COVERAGE", "d-h g"))
    p.append(txt(1140, 30, "each span measured from the source, never estimated", "d-fn", "end"))

    for i, (big, label) in enumerate(COVERAGE_STATS):
        x = 20 + i * 226
        p.append(card(x, 44, 212, 84, "d-box"))
        p.append(txt(x + 106, 92, big, "d-big ok", "middle"))
        p.append(txt(x + 106, 114, label, "d-fn", "middle"))

    half = (len(COVERAGE_BANNERS) + 1) // 2
    for i, (name, badge, span, start) in enumerate(COVERAGE_BANNERS):
        col, row = i // half, i % half
        x = 20 + col * 570
        y = 154 + row * 36
        p.append(f'<rect class="d-ban" x="{x}" y="{y}" width="550" height="30" rx="8"/>')
        p.append(f'<rect class="d-edgemark {badge}" x="{x}" y="{y}" width="4" height="30"/>')
        p.append(txt(x + 16, y + 20, f"{i + 1:02d}", "d-rank"))
        p.append(txt(x + 46, y + 20, name, "d-it"))
        p.append(txt(x + 268, y + 20, BADGE_WORD[badge], f"d-bdg {badge}"))
        if start:
            p.append(txt(x + 400, y + 20, f"{THIS_YEAR - start} yr", "d-yrs"))
        p.append(txt(x + 536, y + 20, span, "d-fn", "end"))

    p.append(txt(20, 560, "Primary means the institution that receives or computes the number, "
                          "not a reseller of it.", "d-fn"))
    p.append(txt(20, 582, "Six verbs reach all of it &middot; source is a parameter, never a "
                          "new tool &middot; twenty more sources adds zero verbs", "d-note"))

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
    "bank":     '<path d="M2.5 8.5 12 3.2l9.5 5.3"/><path d="M2.8 20.5h18.4"/>'
                '<path d="M5.6 10.8v8"/><path d="M9.8 10.8v8"/><path d="M14.2 10.8v8"/>'
                '<path d="M18.4 10.8v8"/>',
    "curve":    '<path d="M3.5 20.5V3.2"/><path d="M3.5 20.5h17"/>'
                '<path d="M4.6 17.4c4.6-7.6 9.4-9.8 15.2-10.6"/>',
    "euro":     '<circle cx="12" cy="12" r="8.5"/>'
                '<path d="M15.8 8.6a4.6 4.6 0 0 0-7.2 3.2 4.6 4.6 0 0 0 7.2 3.4"/>'
                '<path d="M6.8 11h6"/><path d="M6.8 13.4h6"/>',
    "vol":      '<path d="M3.2 20.4h17.6"/><path d="M3.6 14.6 7 7.4l3.6 9.6 3.6-11.8 3.2 7.2 2.6 2.8"/>',
    "short":    '<path d="M3.4 20.6h17.2"/><path d="M6 7.6v13"/><path d="M11 11v9.6"/>'
                '<path d="M16 14.6v6"/><path d="M17.2 5.2h3.4v3.4"/>',
    "scales":   '<path d="M12 3.6v16.6"/><path d="M5.8 20.6h12.4"/><path d="M4 8.2h16"/>'
                '<path d="M7.6 8.2 4.2 14.6h6.8Z"/><path d="M16.4 8.2 13 14.6h6.8Z"/>',
    "book":     '<path d="M12 6.4C10.1 4.8 7.6 4 4.4 4v13.2c3.2 0 5.7.8 7.6 2.4 1.9-1.6 4.4-2.4 7.6-2.4V4c-3.2 0-5.7.8-7.6 2.4Z"/>'
                '<path d="M12 6.4v13.2"/>',
    "delist":   '<path d="M4.5 2.6h8.2l4.4 4.4v14.4H4.5Z"/><path d="M12.7 2.6v4.4h4.4"/>'
                '<path d="M8.2 12.4l5.6 5.6"/><path d="M13.8 12.4l-5.6 5.6"/>',
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
    ("clock", "100", "years, Jul 1926 on"),
    ("stack", str(SOURCE_COUNT), "primary sources"),
    ("scatter", "6", "asset classes"),
    ("gov", "10,398", "tickers mapped"),
    ("series", "800k+", "macro series"),
    ("prompt", str(PREFIX_COUNT), "field prefixes"),
    ("zero", "331", "published claims"),
    ("fall", "36,830", "delistings on record"),
]


# One line of evidence per panel, in place of the paragraph that was there.
FACTS = {
    "__F1__": [("gov", "regulators and central banks"),
               ("school", "universities, not resellers"),
               ("funnel", "one schema out")],
    "__F2__": [("calendar", "July 1926 to this morning"),
               ("prompt", "a source is a parameter"),
               ("stack", "more sources, same six verbs")],
    "__F3__": [("wall", "you never get tomorrow's paper"),
               ("calendar", "a correction is a new edition, not an edit"),
               ("shield", "no print date, no silent guess")],
    "__F5__": [("ledger", "it counts how many times you asked"),
               ("fall", "the Sharpe is deflated for that count"),
               ("shield", "published methods, cited on the page")],
    "__F4__": [("prompt", "one prompt, claim to verdict"),
               ("ledger", "every spec counted this session"),
               ("shield", "every number on this screen reproducible")],
    "__FMAP__": [("stack", "every publisher, its own mark"),
                 ("funnel", "four families into one interface"),
                 ("calendar", "two dates on every row that leaves")],
    "__F6__": [("funnel", "eighteen sources, one grammar"),
               ("prompt", "23 prefixes, six verbs"),
               ("stack", "a new source adds no new tool")],
    "__F7__": [("scatter", "four wire formats in, one row out"),
               ("calendar", "two dates on every row, always"),
               ("shield", "no honest date, no invented one")],
    "__F8__": [("wall", "all six happen to real data"),
               ("fall", "all six flatter a backtest"),
               ("calendar", "known_at is the defence against every one")],
    "__F9__": [("prompt", "plain English in, pandas out"),
               ("ledger", "the restatement shows up as a row"),
               ("shield", "the caveat arrives with the answer")],
    "__F10__": [("ask", "fetched while this page was built"),
                ("clock", "stamped with the minute we read it"),
                ("fall", "no history upstream, so we keep one")],
    "__F11__": [("install", "one command, nothing to clone"),
                ("zero", "no account, no key, no card"),
                ("stack", "same server behind every client")],
}


# What a quant checks before trusting a number. Every one of these is in the
# backtest response today: the first six were always there, and the last five
# arrived with engine/validation.py, which is why the README's "planned" list is
# now shorter. Worded as what the code does, which is why survivorship still
# says warned rather than solved: the delisting record ships, but the universe
# the backtester builds is still current-listing only.
# The rail keeps the four properties of the data itself. The nine properties of
# the backtester moved to the engine slide, where their citations already live,
# so neither list repeats the other.
RAIL_BADGES = [
    ("wall", "point-in-time"),
    ("prompt", "no look-ahead"),
    ("calendar", "restatements"),
    ("shield", "survivorship"),
]

# (glyph, label, what it means on hover). A badge is a claim, and a claim the
# reader cannot unpack is decoration, so each one says what it does in a sentence.
ENGINE_BADGES = [
    ("coin", "turnover cost",
     "Costs charged on every unit of turnover. There is no zero-cost mode to switch on."),
    ("fall", "deflated SR",
     "The Sharpe discounted for how many specifications you tried, "
     "after Bailey and López de Prado (2014)."),
    ("ledger", "trial ledger",
     "Every spec scored this session is counted, and that count is what feeds the deflation."),
    ("stack", "multiple testing",
     "The more ideas you try, the higher the bar a result has to clear to mean anything."),
    ("scatter", "purged k-fold",
     "Train and test folds separated by an embargo, so overlapping label windows "
     "cannot leak across the split."),
    ("funnel", "PBO via CSCV",
     "The probability that the best spec in sample is not the best out of sample, "
     "by combinatorially symmetric cross-validation."),
    ("series", "Newey-West t",
     "A t-statistic corrected for autocorrelated and heteroskedastic returns, "
     "which most monthly strategy returns are."),
    ("flask", "sqrt impact",
     "Market impact that grows with the square root of participation rather than "
     "linearly, so size is not free."),
    ("clock", "min length",
     "How long a backtest has to run before its Sharpe carries any information at all."),
]


def build_badges() -> str:
    # The stagger is per badge rather than one shared loop, so the column reads
    # as eleven separate checks running rather than one thing blinking.
    def pill(glyph: str, label: str, i: int) -> str:
        return (f'<span class="badge" style="--d:{i * -0.42:.2f}s">'
                f'{icon(glyph, 19)}<b>{label}</b></span>')

    engine = "".join(pill(g, lab, i) for i, (g, lab) in enumerate(RAIL_BADGES))
    return (f'<p class="bline">Pipe processed web market data straight into local AI '
            f'agents, on demand.</p>'
            f'<p class="blab eng">Data quality, by construction</p>'
            f'<div class="badges">{engine}</div>')


def arch_src() -> str:
    """The map with a content hash on it. Without one a browser keeps showing
    the copy it cached, which is how a redrawn diagram silently does not ship."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "docs", "architecture.svg")
    try:
        digest = hashlib.md5(io.open(path, "rb").read()).hexdigest()[:10]
    except OSError:
        return "architecture.svg"
    return f"architecture.svg?v={digest}"


def build_tiles() -> str:
    return "\n      ".join(
        f'<div class="tile">{icon(g, 32)}<b>{n}</b><span>{w}</span></div>'
        for g, n, w in TILES)


# The backtest-validation literature, named rather than paraphrased, with what
# is in the code separated from what is not. A terminal claim that cannot show
# its methods is a slogan.
METHODS = [
    ("on", "Point-in-time panel indexed on known_at", "structural, no flag disables it"),
    ("on", "Costs charged on turnover", "there is no zero-cost mode"),
    ("on", "Deflated Sharpe Ratio", "Bailey &amp; L&oacute;pez de Prado, 2014"),
    ("on", "Session trial ledger", "every spec you tried, priced into the result"),
    ("on", "Probability of Backtest Overfitting", "Bailey, Borwein, L&oacute;pez de Prado &amp; Zhu, 2017"),
    ("on", "Purged k-fold with embargo", "Advances in Financial Machine Learning, ch. 7"),
    ("on", "Combinatorial purged CV", "Advances in Financial Machine Learning, ch. 12"),
    ("on", "Minimum Backtest Length", "Bailey, Borwein, L&oacute;pez de Prado &amp; Zhu, 2014"),
    ("on", "Newey-West t-statistic", "Newey &amp; West, 1987"),
    ("on", "Square-root market impact", "Almgren, Thum, Hauptmann &amp; Li, 2005"),
]


def build_methods() -> str:
    rows = "".join(
        f'<div class="method {state}"><b>{name}</b><span>{cite}</span></div>'
        for state, name, cite in METHODS)
    return (f'<div class="mhead"><span class="on">in the code, cited</span>'
            f'</div>{rows}')


def build_engine_badges() -> str:
    return '<div class="ebadges">' + "".join(
        f'<span class="badge tip" style="--d:{i * -0.42:.2f}s" '
        f'data-tip="{html.escape(tip, quote=True)}" tabindex="0">'
        f'{icon(g, 18)}<b>{lab}</b></span>'
        for i, (g, lab, tip) in enumerate(ENGINE_BADGES)) + '</div>'


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
  --sans:"Segoe UI Variable Display","Segoe UI",Inter,"Helvetica Neue",ui-sans-serif,system-ui,sans-serif;
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
  padding:clamp(16px,2.4vh,32px) clamp(20px,2.6vw,40px);
  display:flex;flex-direction:column;gap:clamp(9px,1.5vh,17px);
  border-right:1px solid var(--line);min-width:0;
}
/* The wordmark was mono at 0.17em tracking, which spaced the letters so far
   apart they stopped reading as one word. A tight, heavy grotesque is the
   register a research terminal masthead actually wants. */
.brand{font-family:var(--sans);font-size:clamp(28px,4.8vh,48px);font-weight:800;
  letter-spacing:-.022em;margin:0;line-height:.95;font-variant-ligatures:none;
  display:flex;align-items:center;gap:.34em}

/* A bottle, because that is what a vintage is named after. The label is the
   dated part, and the year mark on it pulses the way the rings used to: the
   thing being claimed is the date, not the wine. */
.brand .mark{width:.92em;height:.92em;flex:0 0 auto;overflow:visible}
.brand .glass{fill:rgba(53,224,138,.09);stroke:var(--green);stroke-width:1.9;
  stroke-linejoin:round}
.brand .cork{fill:none;stroke:var(--green);stroke-width:1.9;stroke-linecap:round}
.brand .label{fill:var(--green);fill-opacity:.16;stroke:var(--green);stroke-width:1.4}
.brand .year{stroke:var(--green);stroke-width:2.2;stroke-linecap:round;
  animation:vintage 4.4s ease-in-out infinite}
.brand .wine{fill:none;stroke:var(--green);stroke-width:1.5;opacity:.45}
@keyframes vintage{
  0%,100%{opacity:.45}
  45%{opacity:1;filter:drop-shadow(0 0 4px var(--green))}}
@media (prefers-reduced-motion:reduce){.brand .year{animation:none;opacity:.9}}
.tag{color:var(--green);letter-spacing:.19em;text-transform:uppercase;font-weight:700;
  font-size:clamp(9px,1.35vh,12px);margin:6px 0 0}
.claim{font-size:clamp(14px,2.15vh,20px);line-height:1.4;margin:0;font-weight:700}
.claim .g{color:var(--green)}
.sub{color:var(--dim);font-size:clamp(11px,1.55vh,13.5px);line-height:1.55;margin:0}

/* six numbers where six sentences used to be */
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);
  border:1px solid var(--line);border-radius:10px;overflow:hidden}
.tile{background:var(--panel);padding:clamp(6px,1.1vh,11px) 6px;display:grid;
  justify-items:center;gap:2px;text-align:center}
.tile .ic{color:var(--green);opacity:.9;stroke-width:1.5}
.tile b{color:var(--ink);font-size:clamp(13px,2vh,18px);line-height:1.1;font-weight:700}
/* what the engine guarantees, one property per badge */
.badges{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}
.bline{margin:0 0 9px;color:var(--ink);font-size:clamp(10.5px,1.45vh,13px);
  line-height:1.45;font-weight:700}
.blab{margin:0 0 4px;color:var(--green);font-size:clamp(9px,1.2vh,11px);
  letter-spacing:.16em;text-transform:uppercase;font-weight:700}
.bsub{margin:-3px 0 6px;color:var(--dim);font-size:clamp(8.5px,1.14vh,10.5px);
  line-height:1.4}
.badge{display:flex;align-items:center;gap:9px;white-space:nowrap;border:1px solid rgba(47,213,135,.28);
  border-radius:9px;padding:7px 10px;background:var(--panel);min-width:0;
  position:relative;overflow:hidden}
/* Each badge is a check the engine runs, so the mark breathes, staggered by --d.
   The pill used to carry a left-to-right sweep as well; two moving things per
   badge was one too many, and the sweep is now the install line's alone. */
.badge .ic{color:var(--green);opacity:.9;flex:none;transform-origin:50% 50%;
  animation:bpulse 3.8s ease-in-out infinite var(--d,0s)}
@keyframes bpulse{0%,100%{opacity:.5;transform:scale(.92)}
  50%{opacity:1;transform:scale(1.08)}}
@media (prefers-reduced-motion:reduce){
  .badge .ic{animation:none;opacity:.9;transform:none}
}
.badge b{color:var(--ink);font-weight:700;line-height:1.2;min-width:0;
  font-size:clamp(10px,1.42vh,13px)}

.tile span{color:var(--dim);font-size:clamp(8.5px,1.15vh,10.5px);line-height:1.25;
  letter-spacing:.04em}


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
.archwrap{flex:1;min-height:0;display:flex;align-items:center;justify-content:center}
.archwrap img{max-width:100%;max-height:100%;width:auto;height:auto;object-fit:contain}
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
.method b{display:block;color:var(--ink);font-size:clamp(11px,1.62vh,15px);
  font-weight:700;line-height:1.3}
.method span{display:block;color:var(--dim);font-size:clamp(9px,1.3vh,12px);
  line-height:1.35}
.method.on{border-left-color:rgba(47,213,135,.7)}
.method.off b{color:var(--dim)}
.mnote{grid-column:1/-1;margin:0;color:var(--dim);font-size:clamp(8px,1.02vh,9.5px);
  line-height:1.4;padding-top:6px;border-top:1px solid var(--line);opacity:.8}
.badge.tip{cursor:help}
.badge.tip::before{content:attr(data-tip);position:absolute;left:50%;bottom:calc(100% + 9px);
  transform:translateX(-50%) translateY(4px);width:max-content;max-width:270px;
  white-space:normal;text-align:left;background:#0b1220;color:var(--ink);
  border:1px solid rgba(47,213,135,.4);border-radius:9px;padding:9px 11px;
  font-size:11.5px;font-weight:400;line-height:1.45;letter-spacing:0;
  box-shadow:0 10px 26px rgba(0,0,0,.55);opacity:0;visibility:hidden;
  transition:opacity .16s ease,transform .16s ease;z-index:40;pointer-events:none}
.badge.tip:hover::before,.badge.tip:focus-visible::before{
  opacity:1;visibility:visible;transform:translateX(-50%) translateY(0)}
.ebadges .badge{overflow:visible}

.ebadges{grid-column:1/-1;display:grid;
  grid-template-columns:repeat(5,minmax(0,1fr));gap:clamp(4px,.7vh,8px);
  margin-bottom:clamp(4px,.7vh,9px)}

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
  padding:clamp(16px,2.6vh,30px) 0 0 clamp(16px,2.2vw,34px)}
/* Eleven chips will not wrap onto one row at any width worth designing for, and
   two rows of chips steal height the panels need. One strip that scrolls
   sideways keeps the bar exactly one line tall however many sections there are;
   the active chip is scrolled into view rather than hunted for. */
.chips{padding-right:clamp(16px,2.2vw,34px);display:flex;flex-wrap:nowrap;gap:7px;margin-bottom:clamp(10px,1.6vh,18px);
  flex:none;overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none;
  scroll-behavior:smooth;padding-bottom:2px}
.chips::-webkit-scrollbar{display:none}
.chip{font-family:var(--mono);font-size:clamp(9px,1.28vh,11.5px);letter-spacing:.11em;
  text-transform:uppercase;color:var(--dim);background:transparent;cursor:pointer;
  border:1px solid var(--line);border-radius:99px;padding:6px 13px;position:relative;
  overflow:hidden;flex:none;white-space:nowrap}
.chip:hover{color:var(--ink)}
.chip.is-on{color:var(--ink);border-color:rgba(47,213,135,.5)}
.chip.is-on::after{content:"";position:absolute;left:0;bottom:0;height:2px;background:var(--green);
  width:100%;transform-origin:left;animation:tick var(--dwell,9s) linear forwards}
@keyframes tick{from{transform:scaleX(0)}to{transform:scaleX(1)}}

/* the six drifts, as cards rather than the long page's list */
.drifts{display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:repeat(2,1fr);
  gap:clamp(8px,1.4vh,16px);flex:1;min-height:0}
/* Slides whose content is a table or a code block, rather than a diagram sized
   to the box, would otherwise sit at the top of a mostly empty screen. */
.fill{flex:1;min-height:0;display:flex;flex-direction:column;justify-content:center}
.panel.inst .fill{justify-content:flex-start;gap:clamp(6px,1vh,12px)}
.drift{display:flex;flex-direction:column;justify-content:center;
  border:1px solid rgba(53,224,138,.22);border-left:3px solid var(--green);border-radius:10px;
  background:var(--panel);padding:clamp(10px,1.8vh,20px) clamp(12px,1.4vw,20px)}
.drift b{display:block;color:var(--ink);font-size:clamp(13px,2.1vh,19px)}
.drift i{display:block;font-style:normal;color:var(--dim);
  font-size:clamp(10.5px,1.6vh,14px);margin-top:5px;line-height:1.45}

/* the live forum board */
.forum{width:100%;border-collapse:collapse;font-size:clamp(10.5px,1.75vh,15px)}
.forum th{color:var(--dim);font-size:clamp(9px,1.25vh,11px);letter-spacing:.12em;
  text-transform:uppercase;text-align:left;padding:0 10px 8px;border-bottom:1px solid var(--line)}
.forum td{padding:clamp(5px,1.1vh,11px) 10px;border-bottom:1px solid var(--line);color:var(--ink)}
.forum td.rk{color:var(--dim);width:2em}
.forum td.tk{font-weight:700;letter-spacing:.04em;color:var(--green)}
.forum td.nm{color:var(--dim)}
.forum .n{text-align:right;font-variant-numeric:tabular-nums}
.forum th.n{text-align:right}
.forum .up{color:var(--green)}
.forum .down{color:var(--red)}
.forum .flat,.forum .dimc{color:var(--dim)}
.stamp{color:var(--dim);font-size:clamp(10px,1.5vh,13px);margin:clamp(8px,1.4vh,16px) 0 0}
.stamp code{color:var(--green)}

/* the install tabs */
.tabs{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:clamp(10px,1.6vh,18px)}
.tab{font-family:var(--mono);font-size:clamp(10px,1.5vh,13px);color:var(--dim);cursor:pointer;
  background:transparent;border:1px solid var(--line);border-radius:99px;padding:6px 14px}
.tab:hover{color:var(--ink)}
.tab.is-on{color:var(--bg);background:var(--green);border-color:var(--green);font-weight:700}
.pane{display:none}
.pane.is-on{display:block}
.pane .note{color:var(--dim);font-size:clamp(11px,1.6vh,14px);margin:0 0 clamp(8px,1.3vh,14px)}
.pane .note code{color:var(--green)}
.pane pre{position:relative;margin:0;background:var(--panel);border:1px solid var(--line);
  border-radius:10px;padding:clamp(12px,1.8vh,20px);overflow:auto;max-height:44vh}
.pane pre code{font-family:var(--mono);font-size:clamp(10.5px,1.65vh,14px);
  color:var(--ink);white-space:pre}


/* the install steps, numbered, beside the client tabs */
.steps{list-style:none;counter-reset:st;margin:0 0 clamp(10px,1.6vh,18px);padding:0;
  display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:clamp(6px,1.1vh,12px)}
.steps li{counter-increment:st;display:grid;grid-template-columns:auto 1fr;
  gap:2px 11px;align-items:baseline}
.steps li::before{content:counter(st);grid-row:span 2;align-self:center;
  width:26px;height:26px;border-radius:50%;border:1px solid rgba(47,213,135,.45);
  color:var(--green);font-size:12px;font-weight:700;display:grid;place-items:center}
.steps b{color:var(--ink);font-size:clamp(11px,1.5vh,14px)}
.steps span{color:var(--dim);font-size:clamp(9.5px,1.3vh,12px);line-height:1.45}
.steps code{color:var(--green)}

/* the drift markers now sit under the point-in-time sweep */
.pit .drifts{display:grid;grid-template-columns:repeat(6,1fr);gap:clamp(5px,0.9vh,10px);
  flex:none;margin-top:clamp(8px,1.3vh,16px)}
.pit .drift{padding:clamp(6px,1vh,11px) clamp(7px,0.8vw,12px)}
.pit .drift b{font-size:clamp(10px,1.4vh,13px)}
.pit .drift i{font-size:clamp(8.5px,1.15vh,11px);margin-top:3px}

.cmd.hot{position:relative;overflow:hidden;border-color:rgba(47,213,135,.45)}
.cmd.hot::after{content:"";position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(105deg,transparent 40%,rgba(47,213,135,.22) 50%,transparent 60%);
  transform:translateX(-100%);animation:cmdflash 4.6s ease-in-out infinite}
@keyframes cmdflash{0%,58%{transform:translateX(-100%)}
  76%{transform:translateX(100%)}100%{transform:translateX(100%)}}
@media (prefers-reduced-motion:reduce){.cmd.hot::after{display:none}}

.panels{position:relative;flex:1;min-height:0;overflow:hidden}
/* Slides travel in the direction you asked for: the incoming panel enters from
   the side you are moving towards and the outgoing one leaves the other way, so
   the deck reads as one strip rather than a stack of cross-fades. --x is set per
   panel by show(), which is what carries the direction. */
/* One roll. Every panel sits side by side on a single track and the track slides;
   nothing fades in or out on its own. That is what makes it read as a continuous
   strip passing across the page rather than a stack of slides swapping places. */
.panel{flex:0 0 100%;max-width:100%;min-width:0;height:100%;
  display:flex;flex-direction:column;opacity:.18;
  transition:opacity .5s cubic-bezier(.22,.61,.36,1);
  padding-right:clamp(16px,2.2vw,34px)}
/* Keyframes rather than a transition: a transition needs the start state to have
   been rendered, and these panels start at visibility:hidden, so the browser was
   skipping straight to the end. An animation has no such requirement. */
.panel.is-on{opacity:1}
.track{display:flex;height:100%;width:100%;will-change:transform;
  transform:translate3d(calc(var(--i,0) * -100%),0,0);
  transition:transform .62s cubic-bezier(.22,.61,.36,1)}}

@media (prefers-reduced-motion:reduce){
  .track{transition:none}
  .panel{opacity:1}
}
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
.d-card{fill:rgba(255,255,255,.018);stroke:rgba(53,224,138,.22)}
.d-box{fill:#070b11;stroke:rgba(53,224,138,.22)}
.d-fam{fill:rgba(255,255,255,.012);stroke:rgba(53,224,138,.22)}
.d-src{fill:#070b11;stroke:var(--line)}
.d-cnt{fill:var(--green);font-size:13px;font-weight:700}
.d-sb{fill:var(--green);font-size:13px;font-weight:700}
.d-raw{fill:var(--dim);font-size:10px}
.d-miss{fill:var(--red);font-size:10px}
.d-exk{fill:var(--dim);font-size:9.5px;letter-spacing:.1em}
.d-exv{fill:var(--green);font-size:11.5px;font-weight:700}
.d-pill{fill:#0c121c;stroke:rgba(47,213,135,.22)}
.d-px{fill:var(--green);font-size:12px;font-weight:700}
.d-ans{fill:var(--dim);font-size:10.5px}
.d-ban{fill:#070b11;stroke:var(--line)}
.d-edgemark{opacity:.85}
.d-edgemark.gov{fill:var(--green)}
.d-edgemark.edu{fill:#2fd587}
.d-edgemark.third{fill:#3b5468}
.d-bdg{font-size:10px;letter-spacing:.16em}
.d-rank{fill:var(--dim);font-size:10px;letter-spacing:.08em}
.d-yrs{fill:var(--ink);font-size:12px;font-weight:700}
.d-bdg.gov{fill:var(--green)}
.d-bdg.edu{fill:#2fd587}
.d-bdg.third{fill:#6b8299}
.d-edge{fill:var(--green);opacity:.55}
.d-pipe{fill:rgba(47,213,135,.05);stroke:rgba(47,213,135,.32)}
.d-stage{fill:#070b11;stroke:rgba(53,224,138,.22)}
.d-num{fill:none;stroke:var(--green);stroke-width:1.3}
.d-numt{fill:var(--green);font-size:11.5px}
.d-st{fill:var(--green);font-size:14.5px;font-weight:700}
.d-ss{fill:var(--dim);font-size:11px}
.d-verb{fill:#0c121c;stroke:rgba(47,213,135,.3)}
.d-vt{fill:var(--green);font-size:13px}
.d-bub{fill:#0c121c;stroke:rgba(53,224,138,.22)}
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
.d-row{fill:#0c121c;stroke:rgba(53,224,138,.22)}
.d-row.warn{stroke:rgba(242,192,118,.5)}
.pit-wall{animation:sweep 11s linear infinite}
@keyframes sweep{to{transform:translateX(920px)}}
.d-track{fill:#0e1723}
.d-fill{fill:var(--green)}
.d-fill.amber{fill:var(--amber)}
.d-fill.bad{fill:var(--red)}
.d-spec{fill:var(--green);opacity:.9}
.d-big{font-size:26px;font-weight:700;fill:var(--ink)}
.d-big.ok{fill:var(--green)}
.d-big.bad{fill:var(--red)}
.d-mid{font-size:20px;font-weight:700;fill:var(--amber)}

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
      <h1 class="brand"><svg class="mark" viewBox="0 0 44 44" aria-hidden="true"><path class="glass" d="M18.5 4h7v9.4c0 1.9.7 2.7 2 4.1 2.4 2.6 3.4 4.6 3.4 8V38a2 2 0 0 1-2 2H15.1a2 2 0 0 1-2-2V25.5c0-3.4 1-5.4 3.4-8 1.3-1.4 2-2.2 2-4.1Z"/><path class="cork" d="M18.6 4.2V2.2h6.8v2"/><rect class="label" x="14.2" y="26.5" width="15.6" height="9.2" rx="1.6"/><path class="year" d="M17.4 31.2h9.2"/><path class="wine" d="M13.4 24.5c2.2-1.1 4.4-1.1 6.6 0s4.4 1.1 6.6 0 4.4-1.1 4.3 0"/></svg><span>VINTAGE</span></h1>
    </div>

    <p class="claim">Good financial data is already free. It&rsquo;s just scattered.
    <span class="g">Vintage federates the web&rsquo;s free financial data in a single MCP server.</span></p>

    <div class="cmd hot"><code>claude mcp add vintage -s user -- uvx vintage-mcp</code><button class="copy" aria-label="Copy">copy</button></div>

    <div class="tiles">
      __TILES__
    </div>

    __BADGES__

    <div class="foot">
      <a href="https://github.com/RezaSoleymanifar/vintage">GitHub</a>
      <a href="https://pypi.org/project/vintage-mcp/">PyPI</a>
      <a href="https://github.com/RezaSoleymanifar/vintage/blob/main/COVERAGE.md">Full catalogue</a>
      <a href="reel.html">Demo reel</a>
      <a href="flows.html">Where the money moved</a>
    </div>
  </aside>

  <main class="stage">
    <div class="chips" id="chips"></div>
    <div class="panels" id="panels">
      <div class="track" id="track">

      <section class="panel arch is-on" data-dwell="14">
        <h2 class="ptitle">The whole thing, on one page.</h2>
        __FMAP__
        <div class="archwrap"><img src="__ARCHSRC__" width="1616" height="980"
          alt="Eighteen free financial data sources: SEC EDGAR, Form 13F, FRED, ECB,
          US Treasury, BLS, BEA, CFTC, CBOE, FINRA, Coinbase, Ken French and more,
          federated behind one interface, every row carrying both the date it
          describes and the date it became public"></div>
      </section>

      <section class="panel" data-dwell="14">
        <h2 class="ptitle">One grammar to name a field, one shape for every row.</h2>
        __F7__
        __DIA6__
      </section>

      <section class="panel" data-dwell="10">
        <h2 class="ptitle">A century of history, and six verbs that reach all of it.</h2>
        __F2__
        __DIA2__
      </section>

      <section class="panel pit" data-dwell="18">
        <h2 class="ptitle">Point-in-time, and the six ways data moves underneath you.</h2>
        __F3__
        __DIA3__
        <div class="drifts">
          __DRIFT__
        </div>
      </section>

      <section class="panel" data-dwell="14">
        <h2 class="ptitle">And a backtester that argues with you.</h2>
        __F5__
        <div class="split">
          <div class="splitdia">__DIA4__</div>
          <div class="methods">
            __EBADGES__
            __METHODS__
            <p class="mnote">Nothing to install past the one line on the left, and the
            engine runs on the same six verbs.</p>
          </div>
        </div>
      </section>

      <section class="panel" data-dwell="28">
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

      <section class="panel" data-dwell="14">
        <h2 class="ptitle">What the forums are saying, right now.</h2>
        __F10__
        <div class="fill">
          __FORUMS__
        </div>
      </section>

      <section class="panel inst" data-dwell="16">
        <h2 class="ptitle">Installed in four steps, none of them a signup.</h2>
        __F11__
        <div class="fill">
          <ol class="steps">
            <li><b>Get <code>uv</code></b><span>One installer, no Python setup.
              <code>pip install uv</code> works too.</span></li>
            <li><b>Add the server</b><span>The line below. Nothing to clone, nothing
              to build, no repository to keep current.</span></li>
            <li><b>Restart the client</b><span>MCP servers load once at startup, so
              a running client will not see it until then.</span></li>
            <li><b>Ask a question</b><span>&ldquo;What were Apple's total assets as of
              January 2020, and has it been restated since?&rdquo;</span></li>
          </ol>
          <div class="tabs">
            __TABS__
          </div>
          __PANES__
        </div>
      </section>

      </div>
    </div>
  </main>
</div>

<script>
(function () {
  var panels = Array.prototype.slice.call(document.querySelectorAll('.panel'));
  var chipbar = document.getElementById('chips');
  var track = document.getElementById('track');
  var titles = ['The map', 'The schema', 'What you get',
                'Point-in-time', 'The engine', 'The experiment', 'The forums',
                'Install'];
  var timer, at = 0, held = false;

  var chips = titles.map(function (t, i) {
    var b = document.createElement('button');
    b.className = 'chip';
    b.textContent = t;
    // Eleven sections on a timer is a two-minute loop, longer than anyone waits.
    // A click is a decision to read this one, so it stops the carousel for good
    // and hands the page over. Browsing should always beat waiting.
    b.addEventListener('click', function () { held = true; show(i); });
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
    // Wrapping from the last slide to the first still reads as "forward", so the
    // loop does not lurch backwards once per cycle.
    at = i;
    panels.forEach(function (p, n) { p.classList.toggle('is-on', n === i); });
    track.style.setProperty('--i', i);
    document.querySelector('.shell').classList.remove('wide');
    var dwell = (parseFloat(panels[i].dataset.dwell) || 9) * 1000;
    chips.forEach(function (c) {
      c.classList.remove('is-on');
      c.style.removeProperty('--dwell');
    });
    if (!held) { chips[i].style.setProperty('--dwell', (dwell / 1000) + 's'); }
    chips[i].classList.add('is-on');
    // The bar scrolls sideways, so the active chip is put in view rather than
    // left off the end where nobody would find it.
    if (chips[i].scrollIntoView) {
      chips[i].scrollIntoView({block: 'nearest', inline: 'center'});
    }
    replay(panels[i]);
    clearTimeout(timer);
    if (!held) {
      timer = setTimeout(function () { show((at + 1) % panels.length); }, dwell);
    }
  }

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    held = true;
    show(0);
  } else {
    show(0);
  }

  // the install panel's client tabs
  document.querySelectorAll('.tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      var wrap = tab.closest('.panel');
      wrap.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('is-on'); });
      wrap.querySelectorAll('.pane').forEach(function (p) { p.classList.remove('is-on'); });
      tab.classList.add('is-on');
      var pane = wrap.querySelector('#' + tab.dataset.pane);
      if (pane) { pane.classList.add('is-on'); }
    });
  });
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
  --sans:"Segoe UI Variable Display","Segoe UI",Inter,"Helvetica Neue",ui-sans-serif,system-ui,sans-serif;
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
    # One session script per terminal panel, each with its own class prefix so the
    # two sets of keyframes cannot collide on the same page.
    rows, anim = build_session(SCRIPT, LOOP, "s")
    exp_rows, exp_anim = build_session(EXPERIMENT, EXPERIMENT_LOOP, "x")
    tabs, panes = build_clients()

    # Diagrams are built before the page is assembled: each one appends its own
    # keyframes to DIA_CSS as a side effect.
    # diagram_federation() is kept, but no slide renders it any more: the source
    # grid it drew was cut. Calling it here would only pour its keyframes into
    # DIA_CSS for nothing.
    dia2, dia3 = diagram_pit(), diagram_honesty()
    taxo = diagram_taxonomy()
    schema = diagram_schema()
    cover = diagram_coverage()
    diacss = "\n".join(DIA_CSS)

    # index.html is the whole site now. The long scrolling page said the same
    # things in the same order, so keeping both meant maintaining one argument
    # twice and letting the two drift apart. Everything that was only on the long
    # page - the six drifts, the live forum board, the session, the install tabs -
    # is a slide here instead.
    one = (
        ONE_PAGE.replace("__DIA5__", taxo)
        .replace("__DIA6__", schema)
        .replace("__DIA2__", cover)
        .replace("__DIA3__", dia2)
        .replace("__EXPROWS__", exp_rows)
        .replace("__ROWS__", rows)
        .replace("__DIA4__", dia3)
        .replace("__DRIFT__", build_drift())
        .replace("__FORUMS__", build_forums())
        .replace("__TABS__", tabs)
        .replace("__PANES__", panes)
        .replace("__EBADGES__", build_engine_badges())
        .replace("__METHODS__", build_methods())
        .replace("__ARCHSRC__", arch_src())
        .replace("__TILES__", build_tiles())
        .replace("__BADGES__", build_badges())
        .replace("__ONECSS__", diacss + "\n" + exp_anim + "\n" + anim)
    )
    for key in FACTS:
        one = one.replace(key, build_facts(key))

    reel_html, reel_css = showcase.build()
    reel = (
        REEL_PAGE.replace("__REEL__", reel_html)
        .replace("__REELCSS__", showcase.STYLE + "\n" + reel_css)
    )

    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
    os.makedirs(root, exist_ok=True)
    for name, body in (("index.html", one), ("reel.html", reel)):
        with open(os.path.join(root, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        print(f"wrote {os.path.join(root, name)} ({len(body):,} bytes)")

    # The long page is gone. Remove it rather than leaving a stale copy of an
    # argument that has moved, since GitHub Pages would happily keep serving it.
    stale = os.path.join(root, "deep.html")
    if os.path.exists(stale):
        os.remove(stale)
        print(f"removed {stale}")


if __name__ == "__main__":
    main()
