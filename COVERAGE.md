# Coverage

What Vintage serves **today**. Generated from the registry by
`tools/build_coverage.py` — if a field is listed here, it is wired up.

For the wider landscape of free data that exists but is not built yet, see
[DATA_SOURCES.md](DATA_SOURCES.md). For the honest limits, see the Known gaps
section of the [README](README.md).

## The six verbs

Source is a parameter, never a separate tool.

| Verb | Takes | Returns |
|---|---|---|
| `resolve` | ticker, CIK, FRED series id, French dataset name | the entity key every other verb accepts |
| `discover` | plain English, optional entity | matching fields across every source's catalog |
| `fetch` | a field, optional entity, optional `as_of` | rows carrying `observed_at` and `known_at` |
| `events` | an entity, optional form filter | filing timeline with exact acceptance timestamps |
| `backtest` | a universe and a signal | returns, costs, and an honesty report |
| `benchmark` | a run id and a factor set | correlation and alpha vs published factors |
| `status` | — | cache size, keys configured, specs tried this session |

## Sources wired up

| Source | Covers | Field form | Point-in-time | Key |
|---|---|---|---|---|
| **sec-edgar-xbrl** | US filer fundamentals, every XBRL concept | `us-gaap:Assets (needs an entity)` | yes — native filing dates | none |
| **sec-edgar-filings** | filing stream: 8-K, 10-K, 10-Q, Form 4, 13D/G | `filing:* (needs an entity)` | yes — exact filing timestamps | none |
| **yahoo-finance** | daily OHLCV and adjusted close, full history unofficial endpoint; Stooq is blocked behind a JS check as of 2026-08 | `price:close / price:adjclose (needs an entity)` | partial — adjusted retroactively | none |
| **ken-french-data-library** | Fama-French factors, momentum, industry portfolios | `french:ff3, french:ff5, french:momentum` | no — rebuilt on each release | none |
| **fred** | 800k macro series, with ALFRED first-release vintages | `fred:CPIAUCSL` | yes — real-time vintages | free key |

## Field prefixes

How a field name routes to a source.

| Prefix | Source | Needs an entity |
|---|---|---|
| `price:` | prices | yes |
| `fred:` | fred | no |
| `french:` | french | no |
| `filing:` | sec-edgar-filings | yes |
| `us-gaap:` | sec-edgar-xbrl | yes |
| `dei:` | sec-edgar-xbrl | yes |
| `ifrs-full:` | sec-edgar-xbrl | yes |
| `srt:` | sec-edgar-xbrl | yes |
| `invest:` | sec-edgar-xbrl | yes |

A bare field with no prefix is routed to `sec-edgar-xbrl`. An unrecognised prefix returns an error naming the prefixes that exist, rather than guessing.

## Ken French datasets (5 wired up)

Dartmouth. The benchmark every factor claim is scored against.

| Field | Dataset | Coverage |
|---|---|---|
| `french:ff3` | Fama-French 3 factors (monthly) | 1926-07-31 → 2026-06-30 |
| `french:ff5` | Fama-French 5 factors (monthly) | 1963-07-31 → 2026-06-30 |
| `french:momentum` | Momentum factor UMD (monthly) | 1927-01-31 → 2026-06-30 |
| `french:ff3_daily` | Fama-French 3 factors (daily) | 1926-07-01 → 2026-06-30 |
| `french:industry49` | 49 industry portfolios (monthly) | 1926-07-31 → 2026-06-30 |

## FRED curated series (12 shortcuts)

Federal Reserve Bank of St. Louis. These are hand-picked so `discover` answers well before a key is configured — but **any** of FRED's 800,000+ series works by id, and ALFRED supplies first-release vintages.

| Field | Series |
|---|---|
| `fred:DGS10` | 10-year Treasury constant maturity yield |
| `fred:DGS2` | 2-year Treasury yield |
| `fred:CPIAUCSL` | CPI, all urban consumers |
| `fred:UNRATE` | Unemployment rate |
| `fred:GDPC1` | Real GDP |
| `fred:FEDFUNDS` | Effective federal funds rate |
| `fred:T10Y2Y` | 10y-2y term spread |
| `fred:BAMLH0A0HYM2` | High-yield credit spread |
| `fred:VIXCLS` | VIX |
| `fred:SOFR` | Secured overnight financing rate |
| `fred:M2SL` | M2 money stock |
| `fred:INDPRO` | Industrial production |

## SEC XBRL fields

Every concept every US filer has tagged is reachable — there is no fixed list, because the
list is per-filer. A large filer exposes roughly 500 concepts across the `us-gaap` and `dei`
taxonomies. Use `discover` against an entity to see what that filer actually reports.

Common starting points: `us-gaap:Assets`, `us-gaap:Revenues`,
`us-gaap:NetIncomeLoss`, `us-gaap:StockholdersEquity`,
`us-gaap:CashAndCashEquivalentsAtCarryingValue`,
`dei:EntityCommonStockSharesOutstanding`.

**Coverage starts around 2009**, when XBRL tagging became mandatory. Anything before that is
in EDGAR as text, not as structured data. This is the single biggest limit on replicating
accounting-based anomalies, whose original samples usually start in the 1960s or 1970s.

## Backtest signals (5 built in)

| Signal | Definition |
|---|---|
| `momentum_12_1` | 12-month return skipping the most recent month (Jegadeesh-Titman) |
| `momentum_6_1` | 6-month return skipping the most recent month |
| `reversal_1m` | negative of last month's return (short-term reversal) |
| `low_volatility` | negative of trailing 12-month volatility |
| `trend_200d` | price relative to its 200-day moving average |

Costs are charged on turnover on every run — there is no zero-cost mode. Returns are computed over 252 trading days per year.
---

Counts and coverage spans measured at generation time. Vintage redistributes none of this data; each upstream source keeps its own terms.
