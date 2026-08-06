# Content audit

Every number and every capability claim in this repository, checked against
what the code actually does. Run on 2026-08-06.

The method was to read the ground truth out of the registry and the source
modules rather than out of the prose, then look for prose that disagreed:

```bash
python -c "import sys; sys.path.insert(0,'src'); from vintage import registry as r; \
  print(len(r.SOURCES), len(r.PREFIXES), sum(1 for s in r.SOURCES if not s['key_required']))"
grep -A3 '^@mcp.tool()' src/vintage/server.py | grep '^async def'
```

## Ground truth

| Fact | Value | Where it comes from |
|---|---|---|
| Sources | 18 | `registry.SOURCES` |
| Sources needing no key | 16 | `key_required` is true only for `fred` and `bea` |
| Field prefixes | 23 | `registry.PREFIXES` |
| Curated macro shortcuts | 12 | `registry.CURATED` |
| Curated indices | 12 | `registry.INDICES` |
| Registered MCP tools | 8 | six verbs, plus `capabilities` and `status` |
| OSAP predictors | 331 | fetched live from SignalDoc |
| OSAP price-only subset | 56 | `openap.supported_only`, fetched live |

## What was wrong

| Claim | Where | Reality | Fixed |
|---|---|---|---|
| "Nine primary sources" | landing page copy, two meta description tags | 18 | says 18 |
| "no API keys" | landing page eyebrow, install note, diagram footer, meta description | FRED and BEA take a free key | says 16 of 18 need no key |
| "Free forever, no key, no account" | the call to action | same | names the two that take one |
| Six verbs, `status` mentioned, `capabilities` not | README | eight tools are registered | both meta tools now named |

Everything else held. The eighteen-source count, the sixteen-keyless count, the
331 predictors, the 56 price-only subset, the six verbs as the data surface, the
1926 start of the Ken French library, and the per-source point-in-time verdicts
in the README table all match the code.

## What cannot be checked from here

Three numbers are quoted from upstream and recorded in the registry as notes.
They were true when measured and nothing in this repository can re-derive them
without a network call:

- 36,830 Form 25 filings across 11,614 companies
- 6,289 filers in one 840 KB frames request
- 800k FRED series

They are attributed to the source in the prose rather than asserted as facts of
this codebase. `COVERAGE.md` is generated from the registry on every build, so
the field-by-field catalogue cannot drift the way hand-written prose can.

## Style pass

The same sweep removed the punctuation and typographic habits that read as
machine-written: 470 em and en dashes across 50 files became ordinary sentence
punctuation, and the status emoji in the README and `DATA_SOURCES.md` tables
became words. Generated files were fixed at their generator, not in the output,
so a rebuild does not undo the pass.
