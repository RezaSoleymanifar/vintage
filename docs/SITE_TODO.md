# Landing page, outstanding

Recorded 2026-08-06. Asked for, not yet built.

## 1. Flash the install line

The one command that matters is styled like every other code block on the
page. It should pulse green so the eye lands on it first — it is the only
thing a first-time visitor has to do.

    claude mcp add vintage -s user -- uvx vintage-mcp

## 2. An install walkthrough, as a slide on the landing page

A short looping clip showing the connector actually being added, so nobody has
to read a config file to believe it works. Two paths, because they are
genuinely different flows:

- **Desktop** — Claude Code one-liner, and the Claude Desktop
  `claude_desktop_config.json` route with the restart step shown.
- **Phone** — how it is reached on mobile, which today means a hosted
  streamable-HTTP endpoint rather than a local stdio server. Worth stating
  plainly on the slide rather than implying parity that does not exist.

Build it the way `assets/demo.gif` is built: CSS keyframes driven from Python,
scrubbed deterministically by `animation-delay`, captured frame by frame. No
screen recording, so it stays sharp and reproducible.

## 3. Carry-overs the redesign dropped

The one-screen rebuild lost two things that were correct before.

- `assets/architecture.svg`, the animated source diagram, is no longer on the
  page at all.
- Three places still say "Nine primary sources". It is eighteen.

## 4. In flight

`UNIVERSE` in `tools/build_site.py` replaces the four grouped text panels with
one orb per source, showing what each one holds. The data and the render loop
are in; the styling for `.d-orb`, the taller viewBox, the larger base type and
the IBM Plex Mono face are not applied yet, so the diagram will render cramped
until they are.
