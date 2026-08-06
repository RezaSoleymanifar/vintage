"""Generate assets/architecture.svg — the flow diagram, animated.

One picture of the whole product: what is scattered across the internet on the
left, what comes out the other side on the right, and packets moving along the
wires between them so it reads as a live system rather than a static box chart.

The source list is pulled from the registry, so the diagram cannot claim a
source the code does not serve.

    uv run python tools/build_diagram.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from vintage import registry  # noqa: E402

W, H = 1280, 700

# Panel metrics, kept together because the vertical layout is derived from them
# and the lanes have to fit between the header and footer rules.
ROW_H = 17
PANEL_HEAD = 40
LANE_GAP = 10
TOP_RULE, BOTTOM_RULE = 72, H - 44

BG = "#0b0f16"
PANEL = "#0e1622"
LINE = "#1f2b3a"
INK = "#e8f1ec"
DIM = "#5f7a8c"
GREEN = "#35e08a"
BLUE = "#7fb3ff"
AMBER = "#ffc46b"
MONO = "ui-monospace,'SF Mono','Cascadia Mono',Menlo,Consolas,monospace"

# Which registry source belongs in which lane. Every source must appear exactly
# once; `check_lanes` fails the build if the registry grows and this does not.
LANES = [
    {
        "title": "REGULATORY FILINGS",
        "note": "primary · US regulator",
        "icon": "doc",
        "accent": GREEN,
        "sources": ["sec-edgar-xbrl", "sec-edgar-filings", "sec-form-13f",
                    "sec-form-25", "sec-xbrl-frames"],
    },
    {
        "title": "MARKET SUPERVISORS",
        "note": "primary · US regulator",
        "icon": "shield",
        "accent": GREEN,
        "sources": ["finra-short-volume", "cftc-cot"],
    },
    {
        "title": "CENTRAL BANKS & AGENCIES",
        "note": "primary · statistical",
        "icon": "bank",
        "accent": BLUE,
        "sources": ["fred", "ecb-reference-rates", "us-treasury", "bls", "bea"],
    },
    {
        "title": "EXCHANGES & PRICES",
        "note": "exchange · third party",
        "icon": "candle",
        "accent": AMBER,
        "sources": ["cboe-indices", "coinbase-exchange", "yahoo-finance"],
    },
    {
        "title": "ACADEMIC & COMMUNITY",
        "note": "primary · academic",
        "icon": "cap",
        "accent": BLUE,
        "sources": ["ken-french-data-library", "open-source-asset-pricing",
                    "apewisdom"],
    },
]

# The short label under each lane, since the registry keys are not display text.
SHORT = {
    "sec-edgar-xbrl": "SEC EDGAR XBRL",
    "sec-edgar-filings": "SEC filing stream",
    "sec-form-13f": "SEC Form 13F",
    "sec-form-25": "SEC Form 25",
    "sec-xbrl-frames": "SEC XBRL frames",
    "finra-short-volume": "FINRA",
    "cftc-cot": "CFTC",
    "fred": "FRED / ALFRED",
    "ecb-reference-rates": "ECB",
    "us-treasury": "US Treasury",
    "bls": "BLS",
    "bea": "BEA",
    "cboe-indices": "CBOE",
    "coinbase-exchange": "Coinbase",
    "yahoo-finance": "Yahoo Finance",
    "ken-french-data-library": "Ken French",
    "open-source-asset-pricing": "Open Source Asset Pricing",
    "apewisdom": "ApeWisdom",
}

ICONS = {
    # Each drawn inside a 20x20 box.
    "doc": ("M4 1.6h8.2l4 4V18.4H4Z", "M12 1.6v4.2h4.2", "M6.6 9h7", "M6.6 12h7",
            "M6.6 15h4.4"),
    "shield": ("M10 1.6 17 4.4v5.8c0 4.6-2.9 7.4-7 8.4-4.1-1-7-3.8-7-8.4V4.4Z",
               "M6.9 10.1 9.1 12.4 13.4 7.9"),
    "bank": ("M2.2 7.4 10 2.6l7.8 4.8", "M2.2 17.9h15.6", "M4.6 9.2v7",
             "M8.2 9.2v7", "M11.8 9.2v7", "M15.4 9.2v7"),
    "candle": ("M4.4 3v14", "M4.4 6h0.1", "M9.9 1.8v16.4", "M15.4 5v11",
               "M2.6 6.2h3.6v7.4H2.6Z", "M8.1 4.6h3.6v9.4H8.1Z",
               "M13.6 7.6h3.6v6.2h-3.6Z"),
    "cap": ("M10 2.4 18.6 6.6 10 10.8 1.4 6.6Z", "M4.6 8.2v4.8c0 1.8 2.4 3.2 5.4 3.2"
            "s5.4-1.4 5.4-3.2V8.2", "M18.6 6.6v5"),
}

# The two-date table on the right, which is the whole reason the product exists.
ENVELOPE = [
    ("us-gaap:Revenues", "2019-09-28", "2019-10-31"),
    ("13f:value", "2024-12-31", "2025-02-14"),
    ("cot:noncomm_net", "2026-07-28", "2026-07-31"),
]

VERBS = ["resolve", "discover", "fetch", "events", "backtest", "benchmark"]
CLIENTS = ["Claude Desktop", "any MCP client", "Python SDK", "notebook"]


def check_lanes() -> None:
    declared = {s["source"] for s in registry.SOURCES}
    placed = [name for lane in LANES for name in lane["sources"]]
    missing = declared - set(placed)
    unknown = set(placed) - declared
    if missing or unknown:
        raise SystemExit(
            f"Diagram lanes are out of step with the registry.\n"
            f"  missing from the diagram: {sorted(missing)}\n"
            f"  not in the registry: {sorted(unknown)}"
        )
    if len(placed) != len(set(placed)):
        raise SystemExit("A source appears in more than one lane.")


def esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def text(x, y, body, *, size=12, fill=INK, weight=400, anchor="start",
         spacing=None, opacity=None) -> str:
    extra = f' letter-spacing="{spacing}"' if spacing else ""
    extra += f' opacity="{opacity}"' if opacity else ""
    return (f'<text x="{x}" y="{y}" font-family="{MONO}" font-size="{size}" '
            f'fill="{fill}" font-weight="{weight}" text-anchor="{anchor}"'
            f'{extra}>{esc(body)}</text>')


def icon(kind: str, x: float, y: float, colour: str, delay: float) -> str:
    strokes = "".join(
        f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="1.4" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        for d in ICONS[kind]
    )
    return (
        f'<g transform="translate({x},{y})" opacity="0.9">{strokes}'
        f'<animate attributeName="opacity" values="0.55;1;0.55" dur="4.2s" '
        f'begin="{delay}s" repeatCount="indefinite"/></g>'
    )


def curve(x1: float, y1: float, x2: float, y2: float) -> str:
    pull = (x2 - x1) * 0.52
    return f"M{x1},{y1} C{x1 + pull},{y1} {x2 - pull},{y2} {x2},{y2}"


def packets(path_id: str, count: int, dur: float, colour: str,
            radius: float = 3.0) -> str:
    """Lights travelling down a wire.

    A negative `begin` starts each one part-way through its cycle, so the line
    is already populated on the first frame rather than filling up over the
    first few seconds.
    """
    out = []
    for i in range(count):
        offset = -dur * i / count
        out.append(
            f'<circle r="{radius}" fill="{colour}" filter="url(#soft)">'
            f'<animateMotion dur="{dur}s" begin="{offset}s" repeatCount="indefinite" '
            # Both spellings: SVG2 `href` and the SVG1.1 `xlink:href` some
            # older renderers still require.
            f'rotate="auto"><mpath href="#{path_id}" xlink:href="#{path_id}"/>'
            f'</animateMotion>'
            f'<animate attributeName="opacity" values="0;1;1;0" '
            f'keyTimes="0;0.12;0.85;1" dur="{dur}s" begin="{offset}s" '
            f'repeatCount="indefinite"/></circle>'
        )
    return "".join(out)


def lane_height(lane: dict) -> float:
    return PANEL_HEAD + len(lane["sources"]) * ROW_H


def lane_panel(lane: dict, x: float, y: float, w: float, index: int) -> tuple[str, float]:
    rows = lane["sources"]
    h = lane_height(lane)
    accent = lane["accent"]
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{PANEL}" '
        f'stroke="{LINE}"/>',
        f'<rect x="{x}" y="{y}" width="3" height="{h}" rx="1.5" fill="{accent}" '
        f'opacity="0.55"/>',
        icon(lane["icon"], x + 15, y + 11, accent, index * 0.5),
        text(x + 44, y + 19, lane["title"], size=10, fill=INK, weight=700, spacing="0.1em"),
        text(x + 44, y + 31, lane["note"], size=8.5, fill=DIM, spacing="0.06em"),
    ]
    for i, name in enumerate(rows):
        row_y = y + PANEL_HEAD + 8 + i * ROW_H
        parts.append(
            f'<circle cx="{x + 20}" cy="{row_y - 4}" r="2.2" fill="{accent}" '
            f'opacity="0.35"><animate attributeName="opacity" '
            f'values="0.25;0.95;0.25" dur="3.4s" begin="{(index * 5 + i) * 0.31:.2f}s" '
            f'repeatCount="indefinite"/></circle>'
        )
        parts.append(text(x + 32, row_y, SHORT[name], size=10.5, fill="#a9c0cf"))
    return "".join(parts), h


def build() -> str:
    check_lanes()

    lane_x, lane_w = 36, 268
    core_x, core_w = 566, 214
    right_x, right_w = 900, 344

    # Lay the lanes out down the left edge, centred in the space between the
    # two rules rather than in the canvas, so nothing rides over the header.
    heights = [lane_height(lane) for lane in LANES]
    block = sum(heights) + LANE_GAP * (len(LANES) - 1)
    top = TOP_RULE + (BOTTOM_RULE - TOP_RULE - block) / 2
    if top < TOP_RULE + 8:
        raise SystemExit(
            f"The lanes need {block:.0f}px but only "
            f"{BOTTOM_RULE - TOP_RULE:.0f}px exist. Raise H or trim ROW_H."
        )

    body: list[str] = []
    wires: list[str] = []
    lights: list[str] = []

    core_y = H / 2 + 6
    core_h = 178
    y = top
    for i, lane in enumerate(LANES):
        panel, h = lane_panel(lane, lane_x, y, lane_w, i)
        body.append(panel)
        # Fan into the core, spread across its left edge.
        target = core_y - 46 + (i * 92 / (len(LANES) - 1))
        pid = f"w{i}"
        wires.append(
            f'<path id="{pid}" d="{curve(lane_x + lane_w, y + h / 2, core_x, target)}" '
            f'fill="none" stroke="{lane["accent"]}" stroke-width="1.1" opacity="0.22"/>'
        )
        lights.append(packets(pid, 3, 3.4 + i * 0.28, lane["accent"]))
        y += h + LANE_GAP

    # ------------------------------------------------------------------ core
    cx, cy = core_x, core_y - core_h / 2
    body.append(
        f'<rect x="{cx - 6}" y="{cy - 6}" width="{core_w + 12}" height="{core_h + 12}" '
        f'rx="16" fill="none" stroke="{GREEN}" stroke-width="1" opacity="0.16">'
        f'<animate attributeName="opacity" values="0.08;0.30;0.08" dur="3.6s" '
        f'repeatCount="indefinite"/></rect>'
    )
    body.append(
        f'<rect x="{cx}" y="{cy}" width="{core_w}" height="{core_h}" rx="12" '
        f'fill="url(#core)" stroke="{GREEN}" stroke-opacity="0.45"/>'
    )
    body.append(text(cx + core_w / 2, cy + 42, "VINTAGE", size=27, fill=INK,
                     weight=700, anchor="middle", spacing="0.2em"))
    body.append(text(cx + core_w / 2, cy + 61, "one interface", size=10, fill=DIM,
                     anchor="middle", spacing="0.16em"))
    body.append(f'<line x1="{cx + 26}" y1="{cy + 78}" x2="{cx + core_w - 26}" '
                f'y2="{cy + 78}" stroke="{LINE}"/>')
    for i, step in enumerate(["resolve the entity", "stamp both dates",
                              "flag what it cannot know"]):
        body.append(
            f'<circle cx="{cx + 30}" cy="{cy + 97 + i * 22 - 4}" r="2.6" '
            f'fill="{GREEN}" opacity="0.4"><animate attributeName="opacity" '
            f'values="0.2;1;0.2" dur="2.4s" begin="{i * 0.8}s" '
            f'repeatCount="indefinite"/></circle>'
        )
        body.append(text(cx + 42, cy + 97 + i * 22, step, size=11, fill="#a9c0cf"))

    body.append(text(cx + core_w / 2, cy + core_h + 34,
                     "one rate-limited HTTP client", size=10, fill=DIM,
                     anchor="middle", spacing="0.06em"))
    body.append(text(cx + core_w / 2, cy + core_h + 50,
                     "nothing stored, nothing redistributed", size=10, fill=DIM,
                     anchor="middle", spacing="0.06em"))

    # ------------------------------------------------------------- the output
    # Three stacked panels, spread evenly between the same two rules.
    env_h, verb_h, out_h = 166, 104, 100
    spare = (BOTTOM_RULE - TOP_RULE) - (env_h + verb_h + out_h)
    step = spare / 4
    env_y = TOP_RULE + step
    verb_y = env_y + env_h + step
    out_y = verb_y + verb_h + step

    body.append(
        f'<rect x="{right_x}" y="{env_y}" width="{right_w}" height="{env_h}" rx="10" '
        f'fill="{PANEL}" stroke="{LINE}"/>'
    )
    body.append(text(right_x + 18, env_y + 26, "EVERY ROW CARRIES TWO DATES",
                     size=10, fill=INK, weight=700, spacing="0.1em"))
    body.append(text(right_x + 18, env_y + 46, "observed_at", size=9.5, fill=DIM,
                     spacing="0.06em"))
    body.append(text(right_x + 18 + 112, env_y + 46, "known_at", size=9.5,
                     fill=GREEN, spacing="0.06em"))
    body.append(text(right_x + 18 + 206, env_y + 46, "field", size=9.5, fill=DIM,
                     spacing="0.06em"))
    for i, (field, observed, known) in enumerate(ENVELOPE):
        row_y = env_y + 70 + i * 28
        body.append(
            f'<rect x="{right_x + 12}" y="{row_y - 14}" width="{right_w - 24}" '
            f'height="24" rx="5" fill="{GREEN}" opacity="0">'
            f'<animate attributeName="opacity" values="0;0.07;0" dur="4.8s" '
            f'begin="{i * 1.6}s" repeatCount="indefinite"/></rect>'
        )
        body.append(text(right_x + 18, row_y, observed, size=11, fill="#a9c0cf"))
        body.append(text(right_x + 18 + 112, row_y, known, size=11, fill=GREEN))
        body.append(text(right_x + 18 + 206, row_y, field, size=9.5, fill=DIM))
    body.append(text(right_x + 18, env_y + 152,
                     "a backtest never sees a row before known_at",
                     size=9.5, fill=AMBER, opacity="0.85"))

    body.append(
        f'<rect x="{right_x}" y="{verb_y}" width="{right_w}" height="{verb_h}" rx="10" '
        f'fill="{PANEL}" stroke="{LINE}"/>'
    )
    body.append(text(right_x + 18, verb_y + 26, "SIX VERBS, NOT EIGHTEEN TOOLS",
                     size=10, fill=INK, weight=700, spacing="0.1em"))
    for i, verb in enumerate(VERBS):
        col, row = i % 3, i // 3
        vx = right_x + 18 + col * 108
        vy = verb_y + 46 + row * 30
        body.append(
            f'<rect x="{vx}" y="{vy}" width="98" height="22" rx="5" fill="#0b111b" '
            f'stroke="{LINE}"/>'
        )
        body.append(text(vx + 49, vy + 15, verb, size=10.5, fill=GREEN,
                         anchor="middle"))

    body.append(
        f'<rect x="{right_x}" y="{out_y}" width="{right_w}" height="{out_h}" rx="10" '
        f'fill="{PANEL}" stroke="{LINE}"/>'
    )
    body.append(text(right_x + 18, out_y + 26, "WHEREVER YOU WORK", size=10,
                     fill=INK, weight=700, spacing="0.1em"))
    for i, client in enumerate(CLIENTS):
        col, row = i % 2, i // 2
        vx = right_x + 18 + col * 158
        vy = out_y + 42 + row * 26
        body.append(
            f'<circle cx="{vx + 5}" cy="{vy + 7}" r="2.4" fill="{BLUE}" '
            f'opacity="0.4"><animate attributeName="opacity" values="0.2;1;0.2" '
            f'dur="3s" begin="{i * 0.7}s" repeatCount="indefinite"/></circle>'
        )
        body.append(text(vx + 16, vy + 11, client, size=10.5, fill="#a9c0cf"))

    # Core out to each right-hand panel.
    for i, panel_mid in enumerate([env_y + env_h / 2, verb_y + verb_h / 2,
                                   out_y + out_h / 2]):
        pid = f"o{i}"
        wires.append(
            f'<path id="{pid}" d="{curve(core_x + core_w, core_y - 30 + i * 30, right_x, panel_mid)}" '
            f'fill="none" stroke="{GREEN if i else BLUE}" stroke-width="1.1" '
            f'opacity="0.22"/>'
        )
        lights.append(packets(pid, 2, 2.9 + i * 0.35, GREEN if i else BLUE, 3.2))

    # --------------------------------------------------------------- chrome
    header = [
        text(36, 40, "VINTAGE", size=15, fill=INK, weight=700, spacing="0.26em"),
        text(36, 58, f"{len(SHORT)} free sources, federated behind one interface",
             size=11, fill=DIM),
        text(W - 36, 40, "every value dated twice", size=11, fill=GREEN,
             anchor="end", spacing="0.08em"),
        text(W - 36, 58, "point-in-time by construction, not by flag", size=10,
             fill=DIM, anchor="end"),
    ]
    footer = [
        text(36, H - 22, "scattered across the internet", size=10, fill=DIM,
             spacing="0.08em"),
        text(core_x + core_w / 2, H - 22, "normalised, stamped, warned about",
             size=10, fill=DIM, anchor="middle", spacing="0.08em"),
        text(W - 36, H - 22, "usable in one question", size=10, fill=DIM,
             anchor="end", spacing="0.08em"),
    ]

    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Vintage architecture: eighteen free financial data sources federated behind one interface, every row carrying both the date it describes and the date it became public">
<title>Vintage — eighteen scattered sources, one interface, every row dated twice</title>
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0%" stop-color="#0b0f16"/><stop offset="52%" stop-color="#0c121c"/>
  <stop offset="100%" stop-color="#090c12"/>
</linearGradient>
<linearGradient id="core" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0%" stop-color="#152a33"/><stop offset="100%" stop-color="#0b131e"/>
</linearGradient>
<pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
  <path d="M40 0H0V40" fill="none" stroke="#141d29" stroke-width="1"/>
</pattern>
<filter id="soft" x="-260%" y="-260%" width="620%" height="620%">
  <feGaussianBlur stdDeviation="2.6" result="b"/>
  <feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
</defs>
<rect width="{W}" height="{H}" fill="url(#bg)"/>
<rect width="{W}" height="{H}" fill="url(#grid)" opacity="0.5"/>
{''.join(header)}
<line x1="36" y1="72" x2="{W - 36}" y2="72" stroke="{LINE}"/>
<line x1="36" y1="{H - 44}" x2="{W - 36}" y2="{H - 44}" stroke="{LINE}"/>
{''.join(wires)}
{''.join(body)}
{''.join(lights)}
{''.join(footer)}
</svg>
"""


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    svg = build()
    # The README reads it from assets/, GitHub Pages serves only docs/, so both
    # are written here rather than left to a copy step someone forgets.
    for folder in ("assets", "docs"):
        out = os.path.join(root, folder, "architecture.svg")
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(svg)
        print(f"wrote {out} ({len(svg):,} bytes)")


if __name__ == "__main__":
    main()
