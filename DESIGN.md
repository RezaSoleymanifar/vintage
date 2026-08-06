# Vintage — architecture

## 1. Verbs, not sources

The obvious design is one tool per source: `get_edgar`, `get_fred`, `get_french`, `get_stooq`… Twenty sources becomes twenty tools, the model burns context reading them, and picks wrong.

Instead: **six verbs, source is a parameter.**

| Verb | Does |
|---|---|
| `resolve` | Any identifier → the spine (ticker, CIK, FIGI, LEI, FRED id, series id) |
| `discover` | Free-text search across every source's catalog → series ids. This is how breadth becomes usable |
| `fetch` | The workhorse. One or many series, date range, `as_of`. Returns tidy rows |
| `events` | Timeline for an entity — 8-Ks, halts, approvals, insider trades, attention spikes |
| `backtest` | Signal spec → returns, costs, honesty report |
| `benchmark` | Your return series → correlation and alpha vs published factors |

Twenty more sources adds zero tools. That is the whole point.

## 2. One envelope

Every value from every source comes back in the same shape. Macro, fundamentals, prices, events — all of it.

```json
{
  "entity": "CIK0000320193",
  "field": "us-gaap:Assets",
  "observed_at": "2019-09-28",
  "known_at": "2019-10-31",
  "value": 338516000000,
  "unit": "USD",
  "source": "sec-edgar-xbrl",
  "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
  "retrieved_at": "2026-08-05T14:02:11Z",
  "vintage": "as-filed"
}
```

Two time columns are the product:

- `observed_at` — what date the value describes
- `known_at` — when you could first have seen it

Sources that cannot supply `known_at` get `"vintage": "UNKNOWN_VINTAGE"` and a null. Never a guess. Same discipline as `paper-to-spec`: cite everything, flag what is unknown.

Because the shape never varies, `backtest` needs no per-source adapters. It filters on `known_at < trade_date` and that is the entire look-ahead guarantee.

## 3. MCP now, HTTP API later — and the reason is legal, not technical

The transport is trivial: the same server already speaks streamable HTTP. The real difference is who fetches the data.

| | Local MCP | Hosted API |
|---|---|---|
| Who calls SEC / Yahoo | The user's machine | **Us** |
| Redistribution | None — user fetched their own | We are redistributing. Licensing exposure |
| Cost | Zero | Ours, and it scales with users |
| Uptime obligation | None | Ours |
| Rate limits | Per user | Pooled — one heavy user degrades everyone |

Local-first is not a limitation, it is what makes "free forever" a promise we can actually keep.

Ship the HTTP API only when non-Claude demand is proven (Cursor, scripts, other agents), and treat it as the paid tier — because it is the version that costs us money.

## 4. Knowing when breadth is right

Do not guess. Instrument it.

- **Log what fails.** Every `discover` and `fetch` that returns nothing is a user asking for data we lack. That log *is* the roadmap, ranked by demand.
- **Fallback rate.** How often does the conversation leave for web search? Falling fallback rate means breadth is landing.
- **The 50-question set.** Keep a fixed list of real quant questions. Breadth is right when they answer end to end without leaving. Add to the list, never remove.
- **Depth beats count.** Ten sources that always answer beat forty that half-answer. Resist adding a source until the 50-question set demands it.

## 5. Making the model use it well, unprompted

Tools that merely return data get used once. Tools that return data *plus a hook* get used all conversation.

1. **Server instructions.** Tell the model how to think about the data, not just what the tools are. Point-in-time is a concept it must hold, not a flag it must remember.
2. **Every response carries flags.** `"warnings": ["3 periods were restated after first filing", "12 tickers in this universe delisted — included"]`. The model surfaces these, the user sees the product catching something, and that is the moment they tell someone.
3. **Every response suggests next steps.** `"suggested_next": [{"verb": "benchmark", "why": "score this against the published UMD series"}]`. Models follow suggestions reliably. This is the self-motivating loop.
4. **Catalog as an MCP resource.** Expose the source catalog as a browsable resource so the model can see what exists without spending a tool call to find out.
5. **Prompts as starters.** Ship MCP prompts — `morning-brief`, `verify-this-factor`, `what-changed-today` — so the good conversations are one click, not a blank page.
6. **Errors that teach.** A miss returns the nearest matches and why it missed, never a bare failure. Already done in `get_fundamentals`.

The compounding effect: warnings make the product look smart, suggestions make the conversation continue, and the continuation produces another warning.

## 6. Cache tiers (planned)

Data that cannot change should never be refetched.

| Data | Refresh |
|---|---|
| Filings and prices from closed periods | Never |
| Ken French, JKP, Open Source Asset Pricing | Monthly |
| Current-quarter fundamentals, macro | Daily |
| Prices, news, events | Per session |

Immutability is decided by `known_at`, not by file age.
