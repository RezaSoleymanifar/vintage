"""Generate docs/index.html — the landing page and its hero animation.

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
    Out(2.5, "vintage connected · 6 tools · 5 sources · 0 API keys", cls="ok"),

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
<title>Vintage — a research terminal that costs $0 and won't lie to you about your Sharpe</title>
<meta name="description" content="Point-in-time financial data from SEC EDGAR, FRED and Ken French behind six verbs, with a backtester that deflates your Sharpe by how many specs you tried.">

<meta property="og:type" content="website">
<meta property="og:title" content="Vintage — a research terminal that costs $0">
<meta property="og:description" content="Point-in-time market data in your chat, and a backtester that counts how many times you asked before it believes you.">
<meta property="og:url" content="https://rezasoleymanifar.github.io/vintage/">
<meta property="og:image" content="https://rezasoleymanifar.github.io/vintage/og.png">
<meta name="twitter:card" content="summary_large_image">

<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%230b0f16'/><path d='M6 22 L13 12 L19 18 L26 8' stroke='%2335e08a' stroke-width='2.6' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>">

<style>
:root{
  --bg:#0b0f16; --panel:#0d1420; --line:#1f2b3a; --grid:#161f2c;
  --ink:#e8f1ec; --dim:#5f7a8c; --green:#35e08a; --red:#ff6b5e; --amber:#ffc46b;
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
.wrap{max-width:1000px;margin:0 auto;padding:0 20px}
a{color:var(--green);text-decoration:none}
a:hover{text-decoration:underline}

/* ------------------------------------------------------------------ hero */
header{padding:60px 0 26px}
h1{
  font-size:clamp(38px,8vw,74px); font-weight:700; letter-spacing:.16em;
  margin:0 0 10px; line-height:1;
}
.sub{color:var(--dim);letter-spacing:.14em;font-size:clamp(11px,2.4vw,15px);margin:0}
.pitch{
  font-size:clamp(17px,3.2vw,23px); line-height:1.45; margin:30px 0 0; max-width:24em;
}
.pitch b{color:var(--green);font-weight:700}

/* -------------------------------------------------------------- terminal */
.term{
  margin:34px 0 0; background:var(--panel); border:1px solid var(--line);
  border-radius:12px; overflow:hidden;
  box-shadow:0 22px 60px -28px rgba(53,224,138,.32);
}
.bar{
  display:flex; align-items:center; gap:8px;
  padding:11px 15px; border-bottom:1px solid var(--line); background:#0a111a;
}
.dot{width:11px;height:11px;border-radius:50%;background:#22303f}
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

/* --------------------------------------------------------------- install */
section{padding:64px 0 0}
h2{font-size:13px;letter-spacing:.24em;color:var(--dim);text-transform:uppercase;margin:0 0 20px;font-weight:400}
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
.copy{
  position:absolute;top:10px;right:10px;font-family:var(--mono);font-size:11.5px;
  letter-spacing:.1em;color:var(--dim);background:#0a111a;border:1px solid var(--line);
  border-radius:6px;padding:5px 10px;cursor:pointer;
}
.copy:hover{color:var(--green);border-color:var(--green)}
.copy.done{color:var(--bg);background:var(--green);border-color:var(--green)}
.after{color:var(--dim);font-size:13.5px;margin:12px 0 0}

/* ------------------------------------------------------------ two dates */
.dates{display:grid;grid-template-columns:1fr;gap:14px;margin-top:6px}
@media(min-width:720px){.dates{grid-template-columns:1fr 1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:18px 19px}
.card h3{margin:0 0 7px;font-size:14px;color:var(--green);letter-spacing:.08em}
.card p{margin:0;color:var(--dim);font-size:14px;line-height:1.6}
.card .val{color:var(--ink)}
.six{display:grid;grid-template-columns:1fr;gap:12px}
@media(min-width:640px){.six{grid-template-columns:1fr 1fr}}
@media(min-width:920px){.six{grid-template-columns:1fr 1fr 1fr}}
.six .card h3{font-size:13px;letter-spacing:.14em;text-transform:uppercase}
.six .card p{font-size:13.5px}
.hl{color:var(--ink);font-weight:700}

table{width:100%;border-collapse:collapse;margin-top:16px;font-size:13.5px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line)}
th{color:var(--dim);font-weight:400;letter-spacing:.1em;font-size:11.5px;text-transform:uppercase}
td.n{color:var(--ink);font-weight:700}
td.was{color:var(--red)}
td.now{color:var(--green)}

.verbs{width:100%;border-collapse:collapse;font-size:14px}
.verbs td{border-bottom:1px solid var(--line);padding:10px 12px;color:var(--dim)}
.verbs td:first-child{color:var(--green);font-weight:700;width:9.5em}

footer{padding:64px 0 70px;color:var(--dim);font-size:13.5px}
footer .links{display:flex;flex-wrap:wrap;gap:18px;margin-bottom:16px}
</style>
</head>
<body>

<div class="wrap">

  <header>
    <h1>VINTAGE</h1>
    <p class="sub">POINT-IN-TIME RESEARCH TERMINAL &middot; MCP</p>
    <p class="pitch">A research terminal that costs <b>$0</b> and won't lie to you about your Sharpe.</p>

    <div class="term">
      <div class="bar">
        <span class="dot"></span><span class="dot"></span><span class="dot"></span>
        <span class="who">claude — vintage</span>
      </div>
      <div class="screen">
        __ROWS__
      </div>
    </div>
  </header>

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

  <section>
    <h2>Every value carries two dates</h2>
    <div class="dates">
      <div class="card">
        <h3>observed_at</h3>
        <p>What period the number describes. <span class="val">Apple's Q4 2019 assets describe September 2019.</span></p>
      </div>
      <div class="card">
        <h3>known_at</h3>
        <p>When it first became public. <span class="val">You could not have traded on it until the 10-K landed in October.</span></p>
      </div>
    </div>
    <p class="after">The backtest panel is indexed on <code>known_at</code>, so any slice of it is
    automatically point-in-time. There is no flag to turn that off. Sources that cannot supply an
    honest <code>known_at</code> are flagged <code>UNKNOWN_VINTAGE</code> rather than given a made-up date.</p>
  </section>

  <section>
    <h2>Six ways yesterday's data quietly changed</h2>
    <div class="six">
      <div class="card"><h3>Lag</h3><p>The number is true in December. It gets published in February.</p></div>
      <div class="card"><h3>Restatement</h3><p>The company says "oops, wrong" and changes last year's number.</p></div>
      <div class="card"><h3>Revision</h3><p>The government keeps fixing old jobs and inflation figures, for years.</p></div>
      <div class="card"><h3>Survivorship</h3><p>Dead companies get deleted. Only the winners are still listed.</p></div>
      <div class="card"><h3>Membership</h3><p>Today's S&amp;P 500 list is not the list from 2005.</p></div>
      <div class="card"><h3>Price adjustment</h3><p>Splits and dividends silently rewrite every price before them.</p></div>
    </div>
    <p class="after">All six say the same thing: <span class="hl">the data you have today is not what
    people saw back then</span>. Point-in-time means showing only what was already public that day —
    and Vintage enforces it in the panel index rather than trusting you to remember.</p>
  </section>

  <section>
    <h2>Why that matters</h2>
    <table>
      <thead><tr><th>What you ask for</th><th>What a normal API returns</th><th>What Vintage returns</th></tr></thead>
      <tbody>
        <tr>
          <td class="n">2019 revenue, asked today</td>
          <td class="was">the restated figure</td>
          <td class="now">both, with the date each was filed</td>
        </tr>
        <tr>
          <td class="n">A universe, as of 2012</td>
          <td class="was">today's survivors</td>
          <td class="now">a warning that it is doing the same, loudly</td>
        </tr>
        <tr>
          <td class="n">A Sharpe, on your 41st idea</td>
          <td class="was">2.14</td>
          <td class="now">0.09 after deflation</td>
        </tr>
      </tbody>
    </table>
  </section>

  <section>
    <h2>Six verbs</h2>
    <table class="verbs">
      <tr><td>resolve</td><td>Any identifier &rarr; the entity key everything else accepts</td></tr>
      <tr><td>discover</td><td>Plain-English search across every source's catalog</td></tr>
      <tr><td>fetch</td><td>The workhorse. Any field, any source, with <code>as_of</code></td></tr>
      <tr><td>events</td><td>Filing timeline with exact public timestamps</td></tr>
      <tr><td>backtest</td><td>Cross-sectional signal &rarr; returns, costs, honesty report</td></tr>
      <tr><td>benchmark</td><td>Your returns &rarr; correlation and alpha vs published factors</td></tr>
    </table>
    <p class="after">Source is a parameter, never a separate tool. Twenty more sources adds zero tools.</p>
  </section>

  <footer>
    <div class="links">
      <a href="https://github.com/RezaSoleymanifar/vintage">GitHub</a>
      <a href="https://pypi.org/project/vintage-mcp/">PyPI</a>
      <a href="https://github.com/RezaSoleymanifar/vintage/blob/main/DATA_SOURCES.md">Data sources</a>
      <a href="https://github.com/RezaSoleymanifar/vintage/blob/main/DESIGN.md">Design</a>
    </div>
    <p>MIT licensed. Vintage redistributes no data — SEC EDGAR, FRED, Yahoo Finance and the
    Ken French library each keep their own terms. Nothing here is investment advice.</p>
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


def main() -> None:
    rows, anim = build_terminal()
    tabs, panes = build_clients()
    page = (
        PAGE.replace("__ROWS__", rows)
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
