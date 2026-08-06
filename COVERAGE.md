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
| **open-source-asset-pricing** | 331 published anomalies with the return and t-stat each paper claimed Chen & Zimmermann. 56 of the 331 are price-only and replicable with Vintage today. | `openap:Mom12m, or openap:* for all of them` | yes — claims are dated to their publication year | none |
| **coinbase-exchange** | crypto OHLCV, every listed pair, no key Currently-listed products only; dead tokens are absent, so crypto survivorship is worse than equities. | `crypto:close (needs an entity like BTC-USD)` | yes — trade prints are never restated | none |
| **finra-short-volume** | daily short volume and short ratio per symbol | `short:short_ratio (needs an entity)` | yes — published after the close, never revised | none |
| **apewisdom** | retail forum mention ranks across ~15 stock and crypto subreddits No history endpoint upstream. Backtestable history starts the day you record it. | `ape:all-stocks, ape:wallstreetbets, ape:all-crypto` | only forward — known_at is when Vintage fetched it | none |
| **ecb-reference-rates** | daily FX reference rates against the euro, 1999 onward, plus cross rates | `fx:EURUSD, fx:USDJPY` | yes — published each afternoon and never revised | none |
| **cboe-indices** | VIX and the volatility family: term structure, VVIX, SKEW Index levels only. Historical option chains are paid everywhere. | `vol:VIX, vol:VIX3M, vol:SKEW` | yes — index levels are not revised | none |
| **sec-form-25** | every delisting on record: 36,830 filings, 11,614 companies, 2003 on The survivorship correction. Complete from April 2006, partial before. | `delisting:form25` | yes — filing dates, never revised | none |
| **fred** | 800k macro series, with ALFRED first-release vintages | `fred:CPIAUCSL` | yes — real-time vintages | free key |

## Field prefixes

How a field name routes to a source.

| Prefix | Source | Needs an entity |
|---|---|---|
| `price:` | prices | yes |
| `fred:` | fred | no |
| `french:` | french | no |
| `openap:` | openap | — |
| `ape:` | apewisdom | — |
| `crypto:` | crypto | — |
| `short:` | finra | — |
| `fx:` | ecb | — |
| `vol:` | cboe | — |
| `delisting:` | delistings | — |
| `index:` | prices | — |
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

## Foreign exchange
European Central Bank reference rates, no key. Published each working day around 16:00 CET and never revised, so these are honestly point-in-time. Everything is quoted against the euro; a cross rate such as `fx:USDJPY` is derived from the two euro legs and labelled as derived.
| Field | Pair |
|---|---|
| `fx:EURUSD` | Euro to USD |
| `fx:EURJPY` | Euro to JPY |
| `fx:EURGBP` | Euro to GBP |
| `fx:EURCHF` | Euro to CHF |
| `fx:EURAUD` | Euro to AUD |
| `fx:EURCAD` | Euro to CAD |
| `fx:EURCNY` | Euro to CNY |
| `fx:EURSEK` | Euro to SEK |
| `fx:EURNOK` | Euro to NOK |
| `fx:EURNZD` | Euro to NZD |

Any ISO code the ECB publishes works, and any two of them cross. History begins in 1999.
## Volatility indices (10)
CBOE, no key. Index levels are computed from that session's option prices and are not revised. **Levels only** — historical option chains are paid at every vendor and remain a gap.
| Field | Covers |
|---|---|
| `vol:VIX` | S&P 500 30-day implied volatility, from 1990 |
| `vol:VIX9D` | S&P 500 9-day implied volatility, from 2011 |
| `vol:VIX3M` | S&P 500 3-month implied volatility, from 2009 |
| `vol:VIX6M` | S&P 500 6-month implied volatility |
| `vol:VVIX` | Volatility of VIX itself, from 2006 |
| `vol:SKEW` | Tail-risk skew of S&P 500 options, from 1990 |
| `vol:VXN` | Nasdaq-100 implied volatility |
| `vol:RVX` | Russell 2000 implied volatility |
| `vol:OVX` | Crude oil ETF implied volatility |
| `vol:GVZ` | Gold ETF implied volatility |

## Market indices
Routed through the price adapter. Listed here because nobody guesses the caret tickers unprompted.
| Entity | Index |
|---|---|
| `^GSPC` | S&P 500 index |
| `^DJI` | Dow Jones Industrial Average |
| `^IXIC` | Nasdaq Composite |
| `^NDX` | Nasdaq-100 |
| `^RUT` | Russell 2000 |
| `^VIX` | VIX (see also vol:VIX) |
| `^FTSE` | FTSE 100 |
| `^GDAXI` | DAX |
| `^N225` | Nikkei 225 |
| `^STOXX50E` | Euro Stoxx 50 |
| `^HSI` | Hang Seng |
| `^TNX` | US 10-year yield |

## Delistings, and survivorship
SEC Form 25 filings: 36,830 covering 11,614 companies, 2003 to 2026, each with a company name, a CIK and an exact date. This is the correction for a universe built from currently-listed names, which is a universe of survivors.
| Field | Returns |
|---|---|
| `delisting:form25` | every delisting on record, dated |

Electronic Form 25 filing became mandatory in April 2006, and the counts show the step: about 450 a year through 2005, 1,421 in 2006, then 1,300 to 2,300 a year. Complete from 2006, partial before, and the response says which.
## Crypto

Coinbase Exchange, no key. A trade print is never restated, so these rows are *more* honestly point-in-time than equity adjusted closes. Survivorship runs the other way: dead tokens are absent entirely, which is a worse bias than equities, not a milder one.

Intervals: `1d`, `6h`, `1h`, `15m`, `5m`, `1m`. All crypto fields need an entity such as `BTC-USD`.

| Field | Returns |
|---|---|
| `crypto:close` | close of each bar |
| `crypto:high` | high of each bar |
| `crypto:low` | low of each bar |
| `crypto:open` | open of each bar |
| `crypto:volume` | volume of each bar |

## Short sale volume

FINRA, published after each close and never revised. This is **short volume, not short interest** — shares sold short during the session, including market-maker hedging that is flat again by the close. A flow measure, not outstanding bearish positioning.

| Field | Returns |
|---|---|
| `short:short_ratio` | short volume as a share of total reported volume |
| `short:short_volume` | shares sold short |
| `short:exempt_volume` | short-exempt shares |
| `short:total_volume` | total reported volume |

One HTTP request per trading day, so `days` defaults to 20 and caps at 90.

## Forum sentiment (7 scopes)

ApeWisdom. No key. **No history endpoint upstream** — every row is stamped `known_at` = the moment Vintage fetched it, so backtestable history begins the day you start recording. Vendors selling years of "historical sentiment" built it by re-scoring archived posts with a model that already knew what happened next.

| Field | Scope |
|---|---|
| `ape:all-stocks` | every tracked stock subreddit |
| `ape:all-crypto` | every tracked crypto subreddit |
| `ape:wallstreetbets` | r/wallstreetbets only |
| `ape:stocks` | r/stocks only |
| `ape:investing` | r/investing only |
| `ape:cryptocurrency` | r/CryptoCurrency only |
| `ape:4chan` | 4chan /biz (beta) |

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
