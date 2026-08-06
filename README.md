<p align="center">
  <img src="assets/banner.svg" alt="Vintage — point-in-time research terminal" width="100%">
</p>

<p align="center">
  <b>A research terminal that costs $0 and won't lie to you about your Sharpe.</b>
</p>

<p align="center">
  <a href="https://pypi.org/project/vintage-mcp/"><img alt="PyPI" src="https://img.shields.io/pypi/v/vintage-mcp?color=35e08a&labelColor=0b0f16"></a>
  <a href="https://github.com/RezaSoleymanifar/vintage/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/RezaSoleymanifar/vintage/ci.yml?branch=main&labelColor=0b0f16"></a>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-35e08a?labelColor=0b0f16"></a>
  <img alt="Python" src="https://img.shields.io/pypi/pyversions/vintage-mcp?labelColor=0b0f16">
</p>

<p align="center">
  <a href="https://rezasoleymanifar.github.io/vintage/"><img src="assets/demo.gif" alt="A Claude session: install Vintage, backtest three signals, watch the deflated Sharpe collapse to 0.09" width="100%"></a>
</p>

<p align="center">
  <a href="https://rezasoleymanifar.github.io/vintage/"><b>rezasoleymanifar.github.io/vintage</b></a>
</p>

---

Free financial data exists and is scattered across twenty APIs with twenty shapes. Everyone rebuilds the same glue, badly, and quietly ends up backtesting on restated figures and survivor-only universes.

Vintage is that glue, written once, served over [MCP](https://modelcontextprotocol.io). It hosts no data — it connects, normalizes, and preserves vintage.

## Install

One line. Nothing to clone.

**Claude Code**

```bash
claude mcp add vintage -s user -- uvx vintage-mcp
```

**Claude Desktop / any MCP client** — add to your config file:

```json
{
  "mcpServers": {
    "vintage": {
      "command": "uvx",
      "args": ["vintage-mcp"]
    }
  }
}
```

<sub>Claude Desktop config lives at `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS). Restart the app afterwards — MCP servers load once at startup.</sub>

Needs [`uv`](https://docs.astral.sh/uv/getting-started/installation/). If you'd rather use pip: `pip install vintage-mcp` and set the command to `vintage`.

### Optional configuration

Everything works with zero configuration. These make it work better:

| Variable | Why |
|---|---|
| `VINTAGE_USER_AGENT` | SEC EDGAR asks for a real contact. `"Your Name your@email.com"`. |
| `FRED_API_KEY` | [Free key](https://fredaccount.stlouisfed.org/apikeys) — unlocks 800k macro series with first-release vintages. |
| `VINTAGE_CACHE_DIR` | Defaults to `~/.cache/vintage`. |

Set them under `"env"` in the same config block:

```json
{
  "mcpServers": {
    "vintage": {
      "command": "uvx",
      "args": ["vintage-mcp"],
      "env": {
        "VINTAGE_USER_AGENT": "Jane Quant jane@example.com",
        "FRED_API_KEY": "..."
      }
    }
  }
}
```

Your key stays in this file. It is read by the server process and is never passed through the model or written into the conversation.

## Try it

Once installed, ask your assistant:

> *"What was Apple's total assets as of January 2020 — and has it been restated since?"*
>
> *"Backtest 12-1 momentum on the Dow 30 since 2010."*
>
> *"Now try short-term reversal instead. Did the alpha survive?"*

The third question is the one that matters. Watch the deflated Sharpe fall as you keep asking.

## The two dates

Every value carries both:

- `observed_at` — what period the number describes
- `known_at` — when it first became public

A backtest may only use rows whose `known_at` precedes the trade date. That is structural, not a setting: the panel is indexed on `known_at`, so any slice of it is automatically point-in-time. There is no flag to turn it off.

Sources that cannot supply an honest `known_at` are flagged `UNKNOWN_VINTAGE` rather than given a fabricated date.

### Six ways yesterday's data quietly changed

- **Lag** — the number is true in December, published in February.
- **Restatement** — the company says "oops, wrong" and changes last year's figure.
- **Revision** — the government keeps fixing old jobs and inflation numbers, for years.
- **Survivorship** — dead companies get deleted; only the winners are still listed.
- **Membership** — today's S&P 500 list is not the list from 2005.
- **Price adjustment** — splits and dividends silently rewrite every price before them.

All six say the same thing: the data you have today is not what people saw back then.

## Six verbs

Source is a parameter, never a separate tool. Twenty more sources adds zero tools.

| Verb | Does |
|---|---|
| `resolve` | Any identifier → the entity key everything else accepts |
| `discover` | Plain-English search across every source's catalog |
| `fetch` | The workhorse. Any field, any source, with `as_of` |
| `events` | Filing timeline with exact public timestamps |
| `backtest` | Cross-sectional signal → returns, costs, honesty report |
| `benchmark` | Your returns → correlation and alpha vs published factors |

Plus `status` for cache size, keys, and how many specs you have tried.

## The honesty engine

A conversational backtester is an overfitting machine unless it counts how many times you asked. Every backtest returns:

- **Deflated Sharpe** ([Bailey & López de Prado, 2014](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)) accounting for every spec tried this session
- **The Sharpe noise would have produced** given that trial count
- **First-half vs second-half Sharpe**
- Costs always charged on turnover — there is no zero-cost mode
- A standing survivorship warning until point-in-time universes land

This is the part a paid terminal does not do for you.

## Sources

| Source | Covers | Key | Point-in-time |
|---|---|---|---|
| SEC EDGAR XBRL | All US filer fundamentals | none | ✅ native filing dates |
| SEC filings stream | 8-K, 10-K/Q, Form 4, 13D/G | none | ✅ exact timestamps |
| Yahoo Finance | Daily OHLCV + adjusted close | none | ⚠️ adjusted retroactively |
| Ken French | FF3, FF5, momentum, industries | none | ❌ rebuilt each release |
| FRED / ALFRED | 800k macro series with vintages | free | ✅ first-release dates |

Stooq was the intended price spine — friendlier terms — but it now gates programmatic access behind a JavaScript check. The adapter stays in case that lifts.

See [`DATA_SOURCES.md`](DATA_SOURCES.md) for the full free-data landscape and [`DESIGN.md`](DESIGN.md) for the architecture.

## Cache

Gzipped JSON in `~/.cache/vintage`, tiered by how mutable the data is: closed periods never refetch, academic datasets monthly, current fundamentals daily, prices per session. An hour of conversation is roughly 20 upstream calls.

## Known gaps

Stated plainly, because the alternative is shipping a bad substitute:

Data:

- **Survivorship** — universes are current-listing only. Form 25 delistings are the next build and the backtester warns until then.
- **Analyst estimates** — no free source exists.
- **Historical options chains** — paid everywhere.
- **Point-in-time index membership** — licensed by S&P and MSCI.

Engine — the backtester is vectorized and cross-sectional, which is a rung below an event-driven simulator:

- **No purging or embargo** — overlapping label windows can leak across a train/test split ([López de Prado, AFML](https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086) ch. 7). Deflation catches selection bias, not leakage.
- **No market impact** — costs are a flat charge on turnover, so large-notional results are optimistic.
- **No PBO** — deflated Sharpe covers multiple testing; the Probability of Backtest Overfitting via combinatorially symmetric cross-validation would be the stronger test.
- **Trial count resets each session** — ask forty things today and forty tomorrow, and tomorrow starts from zero.
- **Sharpe is per observation, not annualized** — that is the frequency the deflation is defined at, and the response says so.

## Development

```bash
git clone https://github.com/RezaSoleymanifar/vintage
cd vintage
uv sync --group dev
uv run pytest
```

`smoke_test.py` exercises all six verbs against the live sources — useful before a release, and it needs network.

## License

MIT. Vintage redistributes no data; each upstream source keeps its own terms.

<sub>mcp-name: io.github.rezasoleymanifar/vintage</sub>
