# Contributing

Vintage federates free financial data behind one interface. The most useful
thing you can add is another source, and that is deliberately a small job: one
file, one prefix, no new tools.

## The rules that decide arguments

These are not style preferences. A pull request that breaks one of them will be
asked to change, however good the data is.

**1. If it cannot be fetched over the internet, it does not exist.** No source
lands on a promise. Probe the endpoint, paste the status code and the payload
size in the pull request. A landing page that returns 200 is not a data source.

**2. Two dates on every row, or an honest admission.** `observed_at` is the
period the value describes. `known_at` is when it first became public. If the
upstream cannot supply the second one, the row gets `known_at = None` and
`vintage = UNKNOWN_VINTAGE`, and the source's `warnings_for` says so in a
sentence a user will understand.

Never invent a date to make the column look full. That is the one thing this
project exists not to do, and it is the fastest way to have a change rejected.

**3. Prefer the body that files, publishes or computes it.** The SEC over a
scraper of the SEC. A central bank over a reseller of central bank data. Not
absolute, but a reseller needs a reason.

**4. Zero new tools.** A source arrives as a field prefix behind `fetch` and
`discover`. The model already knows six verbs; it should not have to learn a
seventh because we added a feed.

## Adding a source

The whole shape, using an existing one as the map:

```
src/vintage/sources/yourname.py     the adapter, one file
src/vintage/registry.py             add the prefix and a SOURCES entry
src/vintage/server.py               one branch in fetch's dispatch
tests/test_yourname.py              conventions, warnings, one network test
```

Read `src/vintage/sources/treasury.py` first. It is the simplest complete
example: a CSV per year, two dates, a catalog, an error that names the valid
tenors instead of saying "not found".

Then read `src/vintage/sources/thirteenf.py`, which is the opposite end. Its
docstring is mostly a list of traps in the data, because that is what the file
is for. Filings before 2023 report market value in thousands and nothing says
so; a manager with sub-advisers files one row per manager per security;
amendments come in two kinds and one of them lists only additions. Every one of
those is a wrong number rather than an error, and catching them is the actual
work.

### What a good adapter does

- Returns `envelope.row(...)` for everything, so the schema cannot drift.
- Raises `SourceError` with a message that teaches. `"No tenor '15y'. Available:
  1m, 3m, 6m, 1y, 2y, 5y, 10y, 30y."` beats a 404 every time.
- Puts the trap in `warnings_for`. If a user could read the data and reach a
  wrong conclusion, that sentence is the most valuable thing in the file.
- Filters upstream where the API allows it, so a request returns kilobytes.
- Uses the shared `http` client, which handles throttling and retries per host.

### What a good test does

Not "does it return rows". The network tests barely matter. What matters:

- The conventions. Does a date parse from every format the source emits.
- The warnings. Does the trap get stated, checked by asserting on the text.
- The errors. Does a wrong input produce a message naming the right ones.

`tests/test_holdings_macro.py` is the pattern. Most of it runs offline against a
fixture pasted from a real payload.

## Sources worth adding

`DATA_ROADMAP.md` has candidates that were probed and returned real payloads,
with sizes and the honest caveat for each. Five are open right now, and two of
them are things that should already exist: Shiller's monthly S&P back to **1871**,
which extends our history fifty-five years past Ken French, and the Welch-Goyal
predictor file that nearly every return-predictability paper is scored against.

## Running things

```bash
uv sync --group dev
uv run pytest -q                 # offline, fast
uv run pytest -q -m network      # hits the real endpoints
uv run python tools/build_coverage.py   # regenerate COVERAGE.md from the registry
```

`COVERAGE.md` is generated. Edit the registry, not the document.

## The bar

The project's whole claim is that it will not lie to you about your Sharpe.
That only survives if every contributor holds the same line: no invented dates,
no silent truncation, no source admitted on a promise. Everything else is
negotiable.
