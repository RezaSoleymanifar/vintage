"""Generate docs/index.html — a diagram-first landing page — and docs/reel.html.

The page makes one claim: Vintage federates the free, point-in-time financial
data of the web. Three architecture diagrams carry almost all of the argument,
so the prose can stay short. Each diagram is inline SVG with CSS-driven motion —
no runtime JS, no libraries, sharp at any size, and a frame grabber can scrub it
deterministically.

  1. Federation  — scattered sources, through four pipeline stages, to six verbs.
  2. Point-in-time — an as-of wall sweeping a timeline, lighting rows as it passes.
  3. Honesty     — 41 specs piling into a trial ledger, collapsing the Sharpe.

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
    Out(6.1, "panel indexed on known_at — lookahead structurally impossible", cls="dim", indent=1),
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

TIERS = [
    ("Regulators", 70, 118, ["SEC EDGAR XBRL", "SEC filings stream", "FINRA short volume"],
     "XBRL JSON · index files · pipe-delimited"),
    ("Central bank", 208, 96, ["FRED", "ALFRED vintages"],
     "CSV · REST · 800k series"),
    ("Academia", 324, 96, ["Ken French Library", "Open Source Asset Pricing"],
     "zipped CSV · Google Drive"),
    ("Markets &amp; crowd", 440, 118, ["Yahoo Finance", "Coinbase Exchange", "ApeWisdom"],
     "chart JSON · REST · no history"),
]

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

    p.append(txt(20, 44, "THE WEB &middot; FREE, PUBLIC, SCATTERED", "d-h"))
    p.append(txt(380, 44, "VINTAGE &middot; THE FEDERATION LAYER", "d-h g"))
    p.append(txt(830, 44, "ONE INTERFACE", "d-h"))

    # ---- left: the sources, grouped by who publishes them
    for tier, y, h, items, foot in TIERS:
        p.append(card(20, y, 250, h))
        p.append(f'<rect class="d-edge" x="20" y="{y + 12}" width="2.5" height="{h - 24}" rx="2"/>')
        p.append(txt(40, y + 24, tier.upper(), "d-ct"))
        for j, it in enumerate(items):
            p.append(txt(40, y + 46 + j * 20, it, "d-it"))
        p.append(txt(40, y + h - 12, foot, "d-fn"))

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
    p.append(txt(400, 524, "nothing hosted &middot; nothing redistributed &middot; no API keys", "d-fn"))

    # ---- wires in
    for i, (_t, y, h, _items, _f) in enumerate(TIERS):
        cy = y + h / 2
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
    ("assets $323.9B &middot; restatement", "filed 30 Oct 2020 &mdash; row 1 stays", 90.5, "warn"),
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
    p.append(txt(40, 96, "41 ideas tried &mdash; every one counted", "d-fn"))

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

# (name, badge, coverage label, bar start %, bar end %) — 1926 on the left.
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
        "Settings → Connectors → Developer mode. Needs a hosted URL — "
        "run <code>vintage</code> behind HTTPS and point the connector at it.",
        "uvx vintage-mcp --transport streamable-http --port 8000",
    ),
]


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

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vintage — the free market research terminal</title>
<meta name="description" content="Vintage federates the free, point-in-time financial data of the web: eighteen primary sources — SEC EDGAR and Form 13F, FRED, US Treasury, BLS, BEA, ECB, CFTC, CBOE, Ken French and more — behind one interface and six verbs. You only ever see what was public that day. No API keys, no cost.">

<meta property="og:type" content="website">
<meta property="og:title" content="Vintage — the free market research terminal">
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
  --mono:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font-family:var(--mono); font-size:16px; line-height:1.55;
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
.copy{position:absolute;top:10px;right:10px;font-family:var(--mono);font-size:11.5px;
  letter-spacing:.1em;color:var(--dim);background:#0a111a;border:1px solid var(--line);
  border-radius:6px;padding:5px 10px;cursor:pointer}
.copy:hover{color:var(--green);border-color:var(--green)}
.copy.done{color:var(--bg);background:var(--green);border-color:var(--green)}

footer{padding:56px 0 70px;color:var(--dim);font-size:12.5px}
footer .links{display:flex;flex-wrap:wrap;gap:18px;margin-bottom:14px;font-size:13.5px}
__DIACSS__
</style>
</head>
<body>

<div class="wrap">

  <header>
    <p class="eyebrow">MCP server &middot; open source &middot; no API keys</p>
    <h1>VINTAGE</h1>
    <p class="sub">Free market research terminal</p>

    <p class="claim">Vintage <span class="g">federates the free, point-in-time financial data of
    the web</span>.</p>
    <p class="gloss"><b>Point-in-time</b> means you only ever see what the world could actually see
    that day. No number that was revised, restated or listed years later leaks backwards into a test
    of the past.</p>
    <p class="pitch">There is no free lunch in market data — the real terminals cost more than a car.
    But most of what they sell is <b>already public and already free</b>, just scattered across a
    dozen government, university and exchange sites in ten incompatible formats, none of them
    keeping track of when anything became known.
    <b>Vintage is the closest thing to a free terminal</b>: one pipeline, one schema, one interface.</p>

    <figure class="arch">
      <img src="architecture.svg" width="1280" height="700" alt="Eighteen free
      financial data sources &mdash; SEC EDGAR, Form 13F, FRED, ECB, US Treasury, BLS, BEA,
      CFTC, CBOE, FINRA, Coinbase, Ken French and more &mdash; federated behind one interface,
      every row carrying both the date it describes and the date it became public">
      <figcaption>Eighteen sources scattered across the internet, one interface,
      every value dated twice.</figcaption>
    </figure>

    <div class="cta">
      <pre class="one"><code>claude mcp add vintage -s user -- uvx vintage-mcp</code><button class="copy" aria-label="Copy">copy</button></pre>
      <p class="ctanote">Free forever &middot; no key &middot; no account</p>
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
    publishes it, factors from the university that computes them &mdash; then four stages that make
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
      <span class="paper off"><b>planned</b> · Newey–West</span>
      <span class="paper off"><b>planned</b> · square-root impact</span>
    </div>
    <p class="after">Execution realism is a different problem, already solved by
    <a href="https://www.quantconnect.com/lean">LEAN</a> and
    <a href="https://nautilustrader.io/">Nautilus Trader</a> — Vintage runs before that, where most
    ideas should die. Citations are references, not endorsements; anything marked planned is not in
    the code yet, and the <code>backtest</code> response says so at runtime.</p>
  </section>

  <section>
    <h2>What it feels like</h2>
    <div class="term">
      <div class="bar">
        <span class="tdot"></span><span class="tdot"></span><span class="tdot"></span>
        <span class="who">claude — vintage</span>
      </div>
      <div class="screen">
        __ROWS__
      </div>
    </div>
    <p class="after">Four more questions answered end to end on the <a href="reel.html">demo reel</a>.</p>
  </section>

  <section>
    <h2>Install</h2>
    <div class="tabs">
      __TABS__
    </div>
    __PANES__
    <p class="after">Needs <a href="https://docs.astral.sh/uv/getting-started/installation/">uv</a>.
    Prefer pip? <code>pip install vintage-mcp</code>, then use <code>vintage</code> as the command.
    No API keys required for anything above.</p>
  </section>

  <footer>
    <div class="links">
      <a href="https://github.com/RezaSoleymanifar/vintage">GitHub</a>
      <a href="https://pypi.org/project/vintage-mcp/">PyPI</a>
      <a href="https://github.com/RezaSoleymanifar/vintage/blob/main/COVERAGE.md">Full data catalogue</a>
      <a href="https://github.com/RezaSoleymanifar/vintage/blob/main/DATA_SOURCES.md">Data landscape</a>
      <a href="https://github.com/RezaSoleymanifar/vintage/blob/main/DESIGN.md">Design</a>
    </div>
    <p>MIT licensed. Vintage redistributes no data — SEC EDGAR, FRED, Yahoo Finance and the
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

REEL_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vintage — demo reel</title>
<meta name="robots" content="noindex">
<style>
:root{
  --bg:#0b0f16; --panel:#0d1420; --line:#1f2b3a;
  --ink:#e8f1ec; --dim:#5f7a8c; --green:#35e08a; --red:#ff6b5e; --amber:#ffc46b;
  --mono:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace;
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
  <h1>Vintage — demo reel &middot; <a href="./">back to the site</a></h1>
  <div class="reel">__REEL__</div>
</div>
</body>
</html>
"""


def main() -> None:
    rows, anim = build_terminal()
    tabs, panes = build_clients()

    # Diagrams are built before the page is assembled: each one appends its own
    # keyframes to DIA_CSS as a side effect.
    dia1, dia2, dia3 = diagram_federation(), diagram_pit(), diagram_honesty()

    page = (
        PAGE.replace("__ROWS__", rows)
        .replace("__DIA1__", dia1)
        .replace("__DIA2__", dia2)
        .replace("__DIA3__", dia3)
        .replace("__DIACSS__", "\n".join(DIA_CSS))
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
    for name, body in (("index.html", page), ("reel.html", reel)):
        with open(os.path.join(root, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        print(f"wrote {os.path.join(root, name)} ({len(body):,} bytes)")


if __name__ == "__main__":
    main()
