"""The showcase reel — a fake screen recording, built from CSS keyframes.

A cursor glides to a target, clicks, the view pushes in on what it hit, the
answer resolves, then it pulls back out and the next scene takes over. Four
scenes, each one a question a portfolio manager would actually ask, in plain
English with no field names in sight.

Everything is keyframes on one shared loop duration, which is what lets the
frame grabber scrub to an exact moment and export the whole thing to GIF and
MP4 without a screen recorder.

Imported by build_site.py. Not run directly.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field

SCENE = 7.0                      # seconds per scene
STAGE_W, STAGE_H = 1000, 520


@dataclass
class Beat:
    """One line of the answer, and when it lands within its scene."""
    at: float                    # seconds from the start of this scene
    kind: str                    # "row" | "big" | "bad" | "note" | "rule" | "strike"
    left: str = ""
    right: str = ""


@dataclass
class Scene:
    ask: str                     # what the cursor "types" — plain English
    caption: str                 # the punchline, held at the end
    click: tuple[int, int]       # where the cursor clicks, in stage coords
    zoom: float                  # how far to push in
    origin: tuple[int, int]      # what to push in on
    beats: list[Beat] = field(default_factory=list)


SCENES = [
    Scene(
        ask="Did Apple ever restate its 2019 revenue?",
        caption="The number changed. Most data feeds only keep the second one.",
        click=(300, 250), zoom=1.20, origin=(500, 250),
        beats=[
            Beat(1.9, "rule", "What Apple reported for FY2019"),
            Beat(2.4, "row", "$338.5 billion", "filed 31 Oct 2019"),
            Beat(3.1, "strike", "$323.9 billion", "restated 30 Oct 2020"),
            Beat(3.9, "note", "Vintage keeps both, and the date of each."),
        ],
    ),
    Scene(
        ask="What was actually public on 1 January 2020?",
        caption="Everything after that date is invisible. By construction, not by setting.",
        click=(600, 230), zoom=1.18, origin=(500, 255),
        beats=[
            Beat(1.9, "rule", "Filings visible on 2020-01-01"),
            Beat(2.3, "row", "10-K, FY2019", "31 Oct 2019"),
            Beat(2.7, "row", "8-K, earnings", "30 Oct 2019"),
            Beat(3.1, "row", "10-Q, Q3", "31 Jul 2019"),
            Beat(3.7, "bad", "10-Q, Q1 2020", "hidden — filed 29 Jan 2020"),
            Beat(4.4, "note", "The future cannot leak in. There is no flag to turn it off."),
        ],
    ),
    Scene(
        ask="Backtest momentum. Then let me try a few more ideas.",
        caption="You asked 41 times. That is what noise looks like.",
        click=(430, 280), zoom=1.20, origin=(500, 262),
        beats=[
            Beat(1.8, "big", "Sharpe", "2.14"),
            Beat(2.6, "row", "specs you tried", "41"),
            Beat(3.2, "row", "Sharpe noise would produce", "2.29"),
            Beat(4.0, "bad", "after adjustment", "0.09"),
            Beat(4.8, "note", "The terminal you pay for does not tell you this."),
        ],
    ),
    Scene(
        ask="Does the published research actually hold up?",
        caption="331 published anomalies, each with the number to beat.",
        click=(420, 240), zoom=1.20, origin=(500, 250),
        beats=[
            Beat(1.9, "rule", "Jegadeesh & Titman, 1993"),
            Beat(2.4, "row", "claimed", "1.31% per month"),
            Beat(2.9, "row", "t-statistic", "3.74"),
            Beat(3.4, "row", "sample", "1964–1989"),
            Beat(4.2, "note", "Now run it yourself, on data that stops where it should."),
        ],
    ),
]

LOOP = SCENE * len(SCENES)

# Where the cursor rests between scenes, so it never teleports.
HOME = (120, 120)


def _pct(t: float) -> float:
    return max(0.0, min(100.0, t / LOOP * 100.0))


def _kf(name: str, stops: list[tuple[float, str]]) -> str:
    body = "".join(f"{_pct(t):.3f}%{{{css}}}" for t, css in stops)
    return f"@keyframes {name}{{{body}}}"


def build() -> tuple[str, str]:
    """Return (html, css) for the reel."""
    markup: list[str] = []
    css: list[str] = []

    cursor_stops: list[tuple[float, str]] = []
    zoom_stops: list[tuple[float, str]] = []

    for i, sc in enumerate(SCENES):
        t0 = i * SCENE
        cx, cy = sc.click
        ox, oy = sc.origin
        origin = f"transform-origin:{ox}px {oy}px"

        # --- cursor: travel in, click, drift, leave -------------------------
        cursor_stops += [
            (t0 + 0.00, f"transform:translate({HOME[0]}px,{HOME[1]}px)"),
            (t0 + 1.25, f"transform:translate({cx}px,{cy}px)"),
            (t0 + 5.60, f"transform:translate({cx + 26}px,{cy + 14}px)"),
            (t0 + 6.55, f"transform:translate({HOME[0]}px,{HOME[1]}px)"),
        ]

        # --- zoom: hold, push in, hold, pull out ---------------------------
        zoom_stops += [
            (t0 + 0.00, f"{origin};transform:scale(1)"),
            (t0 + 1.30, f"{origin};transform:scale(1)"),
            (t0 + 2.10, f"{origin};transform:scale({sc.zoom})"),
            (t0 + 5.55, f"{origin};transform:scale({sc.zoom})"),
            (t0 + 6.35, f"{origin};transform:scale(1)"),
        ]

        # --- click ripple ---------------------------------------------------
        css.append(_kf(f"rip{i}", [
            (t0 + 0.00, "opacity:0;transform:scale(.2)"),
            (t0 + 1.28, "opacity:0;transform:scale(.2)"),
            (t0 + 1.34, "opacity:.85;transform:scale(.35)"),
            (t0 + 1.95, "opacity:0;transform:scale(2.6)"),
            (LOOP - 0.01, "opacity:0;transform:scale(.2)"),
        ]))
        css.append(f".rip{i}{{left:{cx}px;top:{cy}px;animation:rip{i} {LOOP}s infinite}}")

        # --- the scene panel ------------------------------------------------
        css.append(_kf(f"sc{i}", [
            (max(0.0, t0 - 0.35), "opacity:0"),
            (t0 + 0.30, "opacity:1"),
            (t0 + SCENE - 0.55, "opacity:1"),
            (t0 + SCENE - 0.05, "opacity:0"),
        ]))
        css.append(f".sc{i}{{animation:sc{i} {LOOP}s infinite}}")

        # --- the question typing itself -------------------------------------
        n = len(sc.ask)
        css.append(_kf(f"ask{i}", [
            (t0 + 0.10, "width:0"),
            (t0 + 1.20, f"width:{n}ch"),
            (t0 + SCENE - 0.05, f"width:{n}ch"),
        ]))
        css.append(f".ask{i}{{animation:ask{i} {LOOP}s steps({n},end) infinite}}")

        # --- each beat of the answer ----------------------------------------
        beat_html = []
        for j, b in enumerate(sc.beats):
            css.append(_kf(f"b{i}_{j}", [
                (t0 + b.at - 0.30, "opacity:0;transform:translateY(6px)"),
                (t0 + b.at, "opacity:1;transform:none"),
                (t0 + SCENE - 0.30, "opacity:1;transform:none"),
            ]))
            css.append(f".b{i}_{j}{{animation:b{i}_{j} {LOOP}s infinite}}")
            beat_html.append(_beat_markup(b, f"b{i}_{j}"))

        css.append(_kf(f"cap{i}", [
            (t0 + SCENE - 2.30, "opacity:0"),
            (t0 + SCENE - 1.85, "opacity:1"),
            (t0 + SCENE - 0.30, "opacity:1"),
            (t0 + SCENE - 0.05, "opacity:0"),
        ]))
        css.append(f".cap{i}{{animation:cap{i} {LOOP}s infinite}}")

        markup.append(
            f'<div class="scene sc{i}">'
            f'<div class="ask"><span class="q">?</span>'
            f'<span class="asktext ask{i}">{html.escape(sc.ask)}</span></div>'
            f'<div class="answer">{"".join(beat_html)}</div>'
            f'<div class="cap cap{i}">{html.escape(sc.caption)}</div>'
            f"</div>"
        )

    cursor_stops.append((LOOP, f"transform:translate({HOME[0]}px,{HOME[1]}px)"))
    zoom_stops.append((LOOP, "transform:scale(1)"))
    css.append(_kf("cursor", cursor_stops))
    css.append(_kf("zoom", zoom_stops))

    ripples = "".join(f'<span class="rip rip{i}"></span>' for i in range(len(SCENES)))
    dots = "".join(
        f'<span class="dot d{i}"></span>' + _dot_css(css, i) or "" for i in range(len(SCENES))
    )

    stage = (
        '<div class="stage">'
        '<div class="zoomer">'
        f'<div class="scenes">{"".join(markup)}</div>'
        f"{ripples}"
        "</div>"
        '<span class="ptr"></span>'
        f'<div class="dots">{dots}</div>'
        "</div>"
    )
    return stage, "\n".join(css)


def _dot_css(css: list[str], i: int) -> str:
    t0 = i * SCENE
    css.append(_kf(f"dot{i}", [
        (max(0.0, t0 - 0.3), "opacity:.25;width:7px"),
        (t0 + 0.3, "opacity:1;width:22px"),
        (t0 + SCENE - 0.3, "opacity:1;width:22px"),
        (t0 + SCENE, "opacity:.25;width:7px"),
    ]))
    css.append(f".d{i}{{animation:dot{i} {LOOP}s infinite}}")
    return ""


def _beat_markup(b: Beat, cls: str) -> str:
    left, right = html.escape(b.left), html.escape(b.right)
    if b.kind == "rule":
        return f'<div class="brule {cls}">{left}</div>'
    if b.kind == "note":
        return f'<div class="bnote {cls}">{left}</div>'
    if b.kind == "big":
        return f'<div class="bbig {cls}"><span>{left}</span><b>{right}</b></div>'
    if b.kind == "bad":
        return f'<div class="bbad {cls}"><span>{left}</span><b>{right}</b></div>'
    if b.kind == "strike":
        return f'<div class="bstrike {cls}"><span>{left}</span><b>{right}</b></div>'
    return f'<div class="brow {cls}"><span>{left}</span><b>{right}</b></div>'


STYLE = f"""
.reel{{margin:26px 0 0}}
.stage{{
  position:relative;width:100%;max-width:{STAGE_W}px;aspect-ratio:{STAGE_W}/{STAGE_H};
  margin:0 auto;overflow:hidden;border:1px solid var(--line);border-radius:13px;
  background:radial-gradient(120% 120% at 30% 10%,#101a26 0%,#0a0e14 60%);
  container-type:inline-size;
}}
.zoomer{{
  position:absolute;inset:0;animation:zoom {LOOP}s cubic-bezier(.55,.06,.32,1) infinite;
  will-change:transform;
}}
.scenes{{position:absolute;inset:0}}
.scene{{position:absolute;inset:0;opacity:0;padding:5cqw 12cqw 8.5cqw;display:flex;flex-direction:column}}

.ask{{display:flex;align-items:baseline;gap:.7cqw;margin-bottom:2.6cqw}}
.ask .q{{color:var(--green);font-weight:700;font-size:1.95cqw}}
.asktext{{
  display:inline-block;overflow:hidden;white-space:nowrap;width:0;
  color:var(--ink);font-size:1.95cqw;font-weight:700;letter-spacing:.01em;
}}
.answer{{flex:1}}
.cap{{margin-top:auto}}
.brule{{
  color:var(--dim);font-size:1.35cqw;letter-spacing:.22em;text-transform:uppercase;
  padding-bottom:.9cqw;border-bottom:1px solid var(--line);margin-bottom:1.5cqw;opacity:0;
}}
.brow,.bbad,.bstrike,.bbig{{
  display:flex;justify-content:space-between;align-items:baseline;gap:2cqw;
  padding:.75cqw 0;opacity:0;
}}
.brow span,.bbad span,.bstrike span,.bbig span{{color:var(--dim);font-size:1.75cqw}}
.brow b{{color:var(--ink);font-size:2.1cqw}}
.bbig span{{font-size:1.9cqw}}
.bbig b{{color:var(--green);font-size:4.4cqw;line-height:1}}
.bbad b{{color:var(--red);font-size:3.1cqw;line-height:1}}
.bbad span{{color:var(--red);opacity:.75}}
.bstrike b{{color:var(--amber);font-size:2.1cqw}}
.bstrike span{{color:var(--amber);opacity:.8}}
.bnote{{margin-top:1.4cqw;color:var(--dim);font-size:1.6cqw;line-height:1.5;opacity:0}}
.cap{{
  opacity:0;color:var(--ink);font-size:1.9cqw;line-height:1.45;
  border-left:2px solid var(--green);padding-left:1.4cqw;
}}

.ptr{{
  position:absolute;left:0;top:0;width:1.6cqw;height:1.6cqw;pointer-events:none;z-index:5;
  background:var(--ink);clip-path:polygon(0 0,0 78%,26% 60%,44% 96%,62% 88%,44% 52%,74% 50%);
  filter:drop-shadow(0 2px 4px rgba(0,0,0,.65));
  animation:cursor {LOOP}s cubic-bezier(.4,0,.2,1) infinite;
}}
.rip{{
  position:absolute;width:5cqw;height:5cqw;margin:-2.5cqw 0 0 -2.5cqw;border-radius:50%;
  border:2px solid var(--green);opacity:0;pointer-events:none;
}}
.dots{{position:absolute;left:0;right:0;bottom:2.2cqw;display:flex;justify-content:center;gap:.7cqw}}
.dot{{height:7px;width:7px;border-radius:99px;background:var(--green);opacity:.25}}

@media (prefers-reduced-motion:reduce){{
  .zoomer,.ptr,.rip,.dot{{animation:none!important;transform:none!important}}
  .scene{{animation:none!important}}
  .scene:first-child{{opacity:1}}
  .asktext{{width:auto!important;animation:none!important}}
  .brow,.bbad,.bstrike,.bbig,.bnote,.brule,.cap{{opacity:1!important;animation:none!important}}
  .ptr{{display:none}}
}}
"""
