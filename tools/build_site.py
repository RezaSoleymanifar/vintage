"""Generate docs/index.html — a single-screen landing page and its hero animation.

The page answers three questions in order, and nothing else: what is this, what
data is behind it, and what does it do that a free terminal normally cannot.
Everything that used to be a paragraph is now a diagram, a bar, or an icon.

The hero is a fake terminal session driven entirely by CSS keyframes. There is
no JavaScript in the animation on purpose: it stays sharp at any size, it costs
nothing to load, and a frame grabber can capture it deterministically, which is
how assets/demo.gif gets made.

Every line below carries the second it appears at. Edit the script, rerun this,
and the CSS retimes itself.

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


# ------------------------------------------------------------------ sources

# (name, who publishes it, badge kind, the format you get raw, coverage label,
#  bar start %, bar end %) — percentages run 1926 on the left to today on the right.
SOURCES = [
    ("SEC EDGAR XBRL", "U.S. SEC", "gov", "XBRL JSON", "2009 → today", 83, 100),
    ("SEC filings stream", "U.S. SEC", "gov", "index files", "1993 → today", 67, 100),
    ("FRED", "Fed St. Louis", "gov", "CSV / API", "1947 → today", 21, 100),
    ("ALFRED vintages", "Fed St. Louis", "gov", "CSV / API", "1996 → today", 70, 100),
    ("Ken French Library", "Dartmouth", "edu", "zipped CSV", "Jul 1926 → today", 0, 100),
    ("Open Source Asset Pricing", "Chen &amp; Zimmermann", "edu", "Google Drive", "1926 → 2023", 0, 97),
    ("FINRA short volume", "FINRA", "gov", "pipe-delimited", "2009 → today", 83, 100),
    ("Coinbase Exchange", "Coinbase", "third", "REST JSON", "2015 → today", 89, 100),
    ("Yahoo Finance", "Yahoo", "third", "chart JSON", "1962 → today", 36, 100),
    ("ApeWisdom", "community", "third", "REST JSON", "records from today", 99, 100),
]

BADGE_LABEL = {"gov": "regulator", "edu": "academic", "third": "third party"}


def build_scatter() -> str:
    """The top band of the funnel: every source as its own incompatible island."""
    return "\n          ".join(
        f'<span class="chip {badge}"><b>{name}</b>'
        f'<i>{who} · {fmt}</i></span>'
        for name, who, badge, fmt, _span, _a, _b in SOURCES
    )


def build_timeline() -> str:
    rows = []
    for name, _who, badge, _fmt, span, a, b in SOURCES:
        rows.append(
            f'<div class="tl-row">'
            f'<span class="tl-name">{name}</span>'
            f'<span class="tl-track"><i class="tl-bar {badge}" '
            f'style="left:{a}%;width:{max(b - a, 1.2):.1f}%"></i></span>'
            f'<span class="tl-span">{span}</span>'
            f"</div>"
        )
    return "\n        ".join(rows)


VERBS = [
    ("resolve", "any ticker, CIK or name → one entity key", "M4 12h16M12 4l8 8-8 8"),
    ("discover", "plain-English search across every catalog", "M11 4a7 7 0 100 14 7 7 0 000-14zM20 20l-4.2-4.2"),
    ("fetch", "any field, any source, with as_of", "M12 3v12m0 0l-5-5m5 5l5-5M4 20h16"),
    ("events", "filing timeline with exact public timestamps", "M4 6h16M4 12h16M4 18h10"),
    ("backtest", "signal → returns, costs, honesty report", "M4 19V5m0 14h16M7 15l4-5 3 3 5-7"),
    ("benchmark", "your returns → alpha vs published factors", "M12 4v16M6 9v11M18 13v7"),
]


def build_verbs() -> str:
    return "\n          ".join(
        f'<div class="verb">'
        f'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="{path}"/></svg>'
        f"<b>{name}</b><i>{note}</i></div>"
        for name, note, path in VERBS
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
    return "\n          ".join(
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
<meta name="description" content="Free financial data is scattered across a dozen government, university and exchange sites. Vintage unifies it behind one interface — a century of history, nine primary sources, six verbs, no API keys.">

<meta property="og:type" content="website">
<meta property="og:title" content="Vintage — the free market research terminal">
<meta property="og:description" content="Free financial data, scattered across the web, unified behind one interface. A century of history, nine primary sources, six verbs, $0.">
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
svg{display:block}

/* ------------------------------------------------------------------ hero */
header{padding:54px 0 8px}
.eyebrow{
  color:var(--dim);font-size:10.5px;letter-spacing:.24em;text-transform:uppercase;margin:0 0 16px;
}
h1{
  font-size:clamp(38px,8vw,74px); font-weight:700; letter-spacing:.16em;
  margin:0 0 10px; line-height:1;
}
.sub{
  color:var(--green);letter-spacing:.2em;font-size:clamp(11px,2.6vw,16px);margin:0;
  text-transform:uppercase;font-weight:700;
}
.pitch{
  font-size:clamp(17px,3.2vw,24px); line-height:1.45; margin:26px 0 0; max-width:26em; color:var(--dim);
}
.pitch b{color:var(--ink);font-weight:700}
.pitch .g{color:var(--green);font-weight:700}

.cta{margin:26px 0 0;display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center}
.ctanote{margin:0;color:var(--dim);font-size:12.5px}

/* ------------------------------------------------------------- stat strip */
.stats{
  display:grid;grid-template-columns:repeat(2,1fr);gap:1px;margin:30px 0 0;
  background:var(--line);border:1px solid var(--line);border-radius:11px;overflow:hidden;
}
@media(min-width:760px){.stats{grid-template-columns:repeat(6,1fr)}}
.stats div{background:var(--panel);padding:16px 12px;text-align:center}
.stats b{display:block;color:var(--green);font-size:clamp(20px,3.6vw,26px);letter-spacing:.02em}
.stats span{display:block;color:var(--dim);font-size:11px;letter-spacing:.06em;margin-top:5px;line-height:1.35}

/* ---------------------------------------------------------------- section */
section{padding:58px 0 0}
h2{
  font-size:clamp(19px,3.4vw,26px);letter-spacing:.02em;color:var(--ink);
  margin:0 0 8px;font-weight:700;
}
.lede{color:var(--dim);font-size:14.5px;line-height:1.6;margin:0 0 22px;max-width:56em}
.lede .hl{color:var(--ink);font-weight:700}
.after{color:var(--dim);font-size:12.5px;margin:14px 0 0;line-height:1.6}

/* ----------------------------------------------------------- the funnel */
.funnel{margin-top:6px}
.band{
  border:1px solid var(--line);border-radius:12px;background:var(--panel);padding:16px 16px 18px;
}
.blabel{
  display:block;color:var(--dim);font-size:10px;letter-spacing:.22em;text-transform:uppercase;
  margin-bottom:13px;
}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{
  display:block;border:1px solid var(--line);border-radius:8px;padding:8px 11px;
  background:rgba(255,255,255,.015);border-left-width:2px;
}
.chip b{display:block;font-size:12.5px;font-weight:700;line-height:1.3}
.chip i{display:block;font-style:normal;color:var(--dim);font-size:10.5px;margin-top:2px}
.chip.gov{border-left-color:var(--green)}
.chip.edu{border-left-color:var(--blue)}
.chip.third{border-left-color:var(--dim)}

.throat{position:relative;height:112px}
.throat svg{position:absolute;inset:0;width:100%;height:100%}
.throat .hub{
  position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);text-align:center;
  white-space:nowrap;
}
.throat .hub b{
  display:block;color:var(--bg);background:var(--green);border-radius:7px;
  padding:6px 14px;font-size:13px;letter-spacing:.18em;font-weight:700;
}
.throat .hub i{
  display:block;font-style:normal;color:var(--dim);font-size:10.5px;letter-spacing:.1em;margin-top:7px;
}

.band.out{border-color:rgba(53,224,138,.34);background:linear-gradient(180deg,rgba(53,224,138,.06),transparent)}
.verbs{display:grid;grid-template-columns:repeat(2,1fr);gap:9px}
@media(min-width:640px){.verbs{grid-template-columns:repeat(3,1fr)}}
@media(min-width:940px){.verbs{grid-template-columns:repeat(6,1fr)}}
.verb{
  border:1px solid var(--line);border-radius:9px;padding:12px 11px;background:var(--bg);
}
.verb svg{width:19px;height:19px;stroke:var(--green);stroke-width:1.7;fill:none;
  stroke-linecap:round;stroke-linejoin:round;margin-bottom:9px}
.verb b{display:block;color:var(--green);font-size:13px;letter-spacing:.04em}
.verb i{display:block;font-style:normal;color:var(--dim);font-size:11px;line-height:1.45;margin-top:4px}

/* -------------------------------------------------------------- timeline */
.tl{margin-top:26px;border:1px solid var(--line);border-radius:12px;background:var(--panel);padding:18px 16px 14px}
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
.tl-span{font-size:11px;color:var(--dim);text-align:left}
@media(min-width:700px){.tl-span{text-align:right}}

/* --------------------------------------------------------------- terminal */
.term{
  margin:0; background:var(--panel); border:1px solid var(--line);
  border-radius:12px; overflow:hidden;
  box-shadow:0 22px 60px -28px rgba(53,224,138,.32);
}
.bar{
  display:flex; align-items:center; gap:8px;
  padding:11px 15px; border-bottom:1px solid var(--line); background:#0a111a;
}
.tdot{width:11px;height:11px;border-radius:50%;background:#22303f;opacity:1}
.bar .who{margin-left:8px;color:var(--dim);font-size:12.5px;letter-spacing:.1em}
.screen{padding:18px 18px 22px;font-size:clamp(11.5px,2.3vw,14.5px);min-height:352px}

.row{display:flex;align-items:baseline;flex-wrap:wrap;gap:0 8px;padding:1.5px 0;opacity:0}
.in1{padding-left:1.6em}
.prompt{font-weight:700}
.p-shell{color:var(--dim)}
.p-user{color:var(--green)}
.typed{display:inline-block;overflow:hidden;white-space:nowrap;vertical-align:bottom;width:0}
.caret{
  display:inline-block;width:.58em;height:1.05em;background:var(--green);
  vertical-align:text-bottom;visibility:hidden;
}
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
.rule{
  color:var(--dim);letter-spacing:.22em;font-size:.82em;
  margin-top:14px;text-transform:uppercase;gap:12px;
}
.rule i{flex:1;height:1px;background:var(--line);min-width:14px}

@media (prefers-reduced-motion:reduce){
  .row{opacity:1!important;animation:none!important;transform:none!important}
  .typed{width:auto!important;animation:none!important}
  .caret{display:none}
}

/* ------------------------------------------------------------- wow tiles */
.wows{display:grid;grid-template-columns:1fr;gap:14px}
@media(min-width:900px){.wows{grid-template-columns:repeat(3,1fr)}}
.wow{
  border:1px solid var(--line);border-radius:12px;background:var(--panel);
  padding:18px 18px 20px;display:flex;flex-direction:column;
}
.wow .tag{
  display:flex;align-items:center;gap:8px;color:var(--dim);font-size:10px;
  letter-spacing:.2em;text-transform:uppercase;margin-bottom:12px;
}
.wow .tag svg{width:15px;height:15px;stroke:var(--green);stroke-width:1.8;fill:none;
  stroke-linecap:round;stroke-linejoin:round;flex:none}
.wow h3{margin:0 0 14px;font-size:16.5px;line-height:1.35;letter-spacing:.01em}
.wow p{margin:auto 0 0;color:var(--dim);font-size:12.5px;line-height:1.6}
.viz{margin:0 0 16px}

/* two dates */
.dates{position:relative;padding:26px 0 28px}
.dates .axis{height:2px;background:var(--line);position:relative}
.dates .pin{position:absolute;top:-7px;width:12px;height:12px;border-radius:50%;border:2px solid var(--bg)}
.dates .pin.a{left:6%;background:var(--dim)}
.dates .pin.b{left:66%;background:var(--green)}
.dates .gap{
  position:absolute;left:6%;width:60%;top:-1px;height:2px;
  background:repeating-linear-gradient(90deg,var(--red) 0 5px,transparent 5px 10px);
}
.dates .lab{position:absolute;font-size:10.5px;line-height:1.35;white-space:nowrap}
.dates .lab.a{left:0;top:0;color:var(--dim)}
.dates .lab.b{left:52%;top:0;color:var(--green)}
.dates .lab.m{left:4%;top:66px;color:var(--red);font-size:10px;letter-spacing:.06em}
.dates .sp{height:52px}

/* restatement */
.rest{display:grid;gap:8px}
.rest div{display:flex;justify-content:space-between;align-items:baseline;gap:10px;
  border:1px solid var(--line);border-radius:8px;padding:10px 12px}
.rest b{font-size:17px;font-weight:700}
.rest span{color:var(--dim);font-size:10.5px;white-space:nowrap}
.rest .keep{border-color:rgba(53,224,138,.35)}
.rest .keep b{color:var(--green)}
.rest .gone b{color:var(--dim);text-decoration:line-through}

/* sharpe collapse */
.sharpe{display:grid;gap:11px}
.sharpe .lane{display:flex;align-items:center;gap:10px}
.sharpe .num{font-size:23px;font-weight:700;width:2.6em;flex:none}
.sharpe .meter{flex:1;height:11px;border-radius:6px;background:#101927;overflow:hidden}
.sharpe .meter i{display:block;height:11px;border-radius:6px}
.sharpe .a .num{color:var(--green)}
.sharpe .a .meter i{width:93%;background:var(--green)}
.sharpe .b .num{color:var(--red)}
.sharpe .b .meter i{width:4%;background:var(--red)}
.sharpe .mid{color:var(--amber);font-size:11px;letter-spacing:.06em;text-align:center}

/* -------------------------------------------------------------- drift row */
.drifts{display:grid;grid-template-columns:1fr;gap:9px;margin-top:16px}
@media(min-width:600px){.drifts{grid-template-columns:repeat(2,1fr)}}
@media(min-width:940px){.drifts{grid-template-columns:repeat(3,1fr)}}
.drift{display:block;border-left:2px solid var(--amber);padding:2px 0 2px 11px}
.drift b{display:block;font-size:12.5px}
.drift i{display:block;font-style:normal;color:var(--dim);font-size:11.5px;margin-top:1px}

/* ---------------------------------------------------------------- method */
.papers{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}
.paper{border:1px solid var(--line);border-radius:7px;padding:7px 11px;font-size:11.5px;color:var(--dim)}
.paper b{color:var(--ink);font-weight:700}
.paper.on{border-color:rgba(53,224,138,.4);background:rgba(53,224,138,.07)}
.paper.on b{color:var(--green)}
.paper.off b{color:var(--amber)}

/* --------------------------------------------------------------- install */
.tabs{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:14px}
.tab{
  font-family:var(--mono);font-size:13px;color:var(--dim);cursor:pointer;
  background:transparent;border:1px solid var(--line);border-radius:7px;padding:7px 13px;
}
.tab:hover{color:var(--ink)}
.tab.is-on{color:var(--bg);background:var(--green);border-color:var(--green);font-weight:700}
.pane{display:none}
.pane.is-on{display:block}
.note{color:var(--dim);font-size:14px;margin:0 0 11px}
.note code{color:var(--ink)}
pre{
  position:relative;margin:0;background:var(--panel);border:1px solid var(--line);
  border-radius:10px;padding:15px 74px 15px 16px;overflow-x:auto;
  font-size:13.5px;line-height:1.65;color:var(--green);
}
pre.one{flex:1 1 30em;padding:14px 74px 14px 16px;font-size:clamp(11.5px,2.2vw,13.5px)}
.copy{
  position:absolute;top:10px;right:10px;font-family:var(--mono);font-size:11.5px;
  letter-spacing:.1em;color:var(--dim);background:#0a111a;border:1px solid var(--line);
  border-radius:6px;padding:5px 10px;cursor:pointer;
}
.copy:hover{color:var(--green);border-color:var(--green)}
.copy.done{color:var(--bg);background:var(--green);border-color:var(--green)}

footer{padding:56px 0 70px;color:var(--dim);font-size:12.5px}
footer .links{display:flex;flex-wrap:wrap;gap:18px;margin-bottom:14px;font-size:13.5px}
</style>
</head>
<body>

<div class="wrap">

  <header>
    <p class="eyebrow">MCP server &middot; open source &middot; no API keys</p>
    <h1>VINTAGE</h1>
    <p class="sub">Free market research terminal</p>
    <p class="pitch">The good financial data is already <b>free</b> — it is just
    <b>scattered</b> across a dozen government, university and exchange websites, in ten
    different formats. Vintage <span class="g">unifies all of it behind one interface</span>.</p>

    <div class="cta">
      <pre class="one"><code>claude mcp add vintage -s user -- uvx vintage-mcp</code><button class="copy" aria-label="Copy">copy</button></pre>
      <p class="ctanote">Free forever &middot; no key &middot; no account</p>
    </div>

    <div class="stats">
      <div><b>$0</b><span>total cost</span></div>
      <div><b>100</b><span>years of history</span></div>
      <div><b>9</b><span>primary sources</span></div>
      <div><b>6</b><span>verbs, that's the API</span></div>
      <div><b>800k+</b><span>macro series</span></div>
      <div><b>331</b><span>published anomalies</span></div>
    </div>
  </header>

  <section>
    <h2>What data?</h2>
    <p class="lede">The filings come from the regulator that receives them, the macro from the
    central bank that publishes it, the factors from the university that computes them.
    <span class="hl">Primary sources, not a scrape of someone else's mirror.</span>
    Vintage hosts none of it — it connects, normalizes, and preserves vintage.</p>

    <div class="funnel">
      <div class="band">
        <span class="blabel">Scattered · ten formats · nobody's job to glue them</span>
        <div class="chips">
          __CHIPS__
        </div>
      </div>

      <div class="throat">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <path d="M0 0 L100 0 L64 100 L36 100 Z" fill="rgba(53,224,138,.07)"/>
          <path d="M0 0 L36 100" stroke="#1f2b3a" stroke-width=".4" vector-effect="non-scaling-stroke" fill="none"/>
          <path d="M100 0 L64 100" stroke="#1f2b3a" stroke-width=".4" vector-effect="non-scaling-stroke" fill="none"/>
        </svg>
        <span class="hub"><b>VINTAGE</b><i>one schema · two dates on every value</i></span>
      </div>

      <div class="band out">
        <span class="blabel">Unified · source is a parameter, never a new tool</span>
        <div class="verbs">
          __VERBS__
        </div>
      </div>
    </div>

    <div class="tl">
      <div class="tl-head"><span>1926</span><span>coverage</span><span>today</span></div>
      __TIMELINE__
    </div>
    <p class="after"><a href="https://github.com/RezaSoleymanifar/vintage/blob/main/COVERAGE.md">The
    full field-by-field catalogue</a> is generated from the registry, so it cannot drift from the
    code. Each upstream source keeps its own terms; Vintage redistributes none of it.</p>
  </section>

  <section>
    <h2>What does it do?</h2>
    <p class="lede">You ask in plain English. It pulls the data, builds a point-in-time panel,
    runs the backtest, charges the costs — and then <span class="hl">tells you how much of your
    result is luck</span>.</p>

    <div class="term">
      <div class="bar">
        <span class="tdot"></span><span class="tdot"></span><span class="tdot"></span>
        <span class="who">claude — vintage</span>
      </div>
      <div class="screen">
        __ROWS__
      </div>
    </div>
  </section>

  <section>
    <h2>Three things the terminal you pay for won't do</h2>
    <p class="lede">This is the whole product, in three pictures.</p>

    <div class="wows">

      <div class="wow">
        <span class="tag"><svg viewBox="0 0 24 24"><path d="M12 7v5l3 2"/><circle cx="12" cy="12" r="8"/></svg>two dates, always</span>
        <h3>Every value knows when it became public</h3>
        <div class="viz dates">
          <span class="lab a">observed_at<br>Sep 2019</span>
          <span class="lab b">known_at<br>31 Oct 2019</span>
          <div class="sp"></div>
          <div class="axis">
            <span class="gap"></span>
            <span class="pin a"></span>
            <span class="pin b"></span>
          </div>
          <span class="lab m">◀ you could not have traded here ▶</span>
        </div>
        <p>The panel is indexed on <code>known_at</code>, so every slice is point-in-time by
        construction. There is no flag to turn it off.</p>
      </div>

      <div class="wow">
        <span class="tag"><svg viewBox="0 0 24 24"><path d="M4 8h12l-3-3M20 16H8l3 3"/></svg>history is kept</span>
        <h3>Apple's 2019 revenue, both versions</h3>
        <div class="viz rest">
          <div class="keep"><b>$338.5B</b><span>filed 31 Oct 2019</span></div>
          <div class="gone"><b>$323.9B</b><span>restated 30 Oct 2020</span></div>
        </div>
        <p>Most feeds overwrite the first number with the second. Vintage keeps both rows and the
        accession number of each, so your 2019 backtest sees what 2019 saw.</p>
      </div>

      <div class="wow">
        <span class="tag"><svg viewBox="0 0 24 24"><path d="M12 3v10m0 4v1"/><path d="M3 20h18L12 4z"/></svg>honesty report</span>
        <h3>Your Sharpe, after counting the tries</h3>
        <div class="viz sharpe">
          <div class="lane a"><span class="num">2.14</span><span class="meter"><i></i></span></div>
          <div class="mid">41 specs tried this session ▾</div>
          <div class="lane b"><span class="num">0.09</span><span class="meter"><i></i></span></div>
        </div>
        <p>Deflated Sharpe (Bailey &amp; López de Prado). Vintage counts every spec you tried in
        the session and deflates the result by it — automatically, out loud.</p>
      </div>

    </div>

    <p class="after"><span class="hl" style="color:var(--ink)">Why any of this is needed:</span>
    six ways yesterday's data quietly changed underneath you.</p>
    <div class="drifts">
      __DRIFT__
    </div>

    <p class="after">Vintage implements the backtest-validation literature rather than inventing its
    own statistics. Execution realism is a different problem, already solved by
    <a href="https://www.quantconnect.com/lean">LEAN</a> and
    <a href="https://nautilustrader.io/">Nautilus Trader</a> — Vintage runs before that, where most
    ideas should die.</p>
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
    <p class="after">Citations are references, not endorsements. Anything marked planned is not in
    the code yet, and the <code>backtest</code> response says so at runtime rather than in a footnote.</p>
  </section>

  <section>
    <h2>Four questions, answered live</h2>
    <div class="reel">__REEL__</div>
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

<style>__ANIM__
__REELCSS__</style>

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


def main() -> None:
    rows, anim = build_terminal()
    tabs, panes = build_clients()
    reel_html, reel_css = showcase.build()
    page = (
        PAGE.replace("__ROWS__", rows)
        .replace("__CHIPS__", build_scatter())
        .replace("__VERBS__", build_verbs())
        .replace("__TIMELINE__", build_timeline())
        .replace("__DRIFT__", build_drift())
        .replace("__REEL__", reel_html)
        .replace("__REELCSS__", showcase.STYLE + "\n" + reel_css)
        .replace("__TABS__", tabs)
        .replace("__PANES__", panes)
        .replace("__ANIM__", anim)
    )
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
    os.makedirs(root, exist_ok=True)
    out = os.path.join(root, "index.html")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    print(f"wrote {out} ({len(page):,} bytes, {LOOP}s loop)")


if __name__ == "__main__":
    main()
