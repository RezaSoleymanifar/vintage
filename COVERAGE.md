# Coverage

What Vintage serves **today**. Generated from the registry by
`tools/build_coverage.py`: if a field is listed here, it is wired up.

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
| `status` | none | cache size, keys configured, specs tried this session |

## Sources wired up

| Source | Covers | Field form | Point-in-time | Key |
|---|---|---|---|---|
| **sec-edgar-xbrl** | US filer fundamentals, every XBRL concept | `us-gaap:Assets (needs an entity)` | yes, native filing dates | none |
| **sec-edgar-filings** | filing stream: 8-K, 10-K, 10-Q, Form 4, 13D/G | `filing:* (needs an entity)` | yes, exact filing timestamps | none |
| **yahoo-finance** | daily OHLCV and adjusted close, full history unofficial endpoint; Stooq is blocked behind a JS check as of 2026-08 | `price:close / price:adjclose (needs an entity)` | partial, adjusted retroactively | none |
| **ken-french-data-library** | Fama-French factors, momentum, industry portfolios | `french:ff3, french:ff5, french:momentum` | no, rebuilt on each release | none |
| **open-source-asset-pricing** | 331 published anomalies with the return and t-stat each paper claimed Chen & Zimmermann. 56 of the 331 are price-only and replicable with Vintage today. | `openap:Mom12m, or openap:* for all of them` | yes, claims are dated to their publication year | none |
| **coinbase-exchange** | crypto OHLCV, every listed pair, no key Currently-listed products only; dead tokens are absent, so crypto survivorship is worse than equities. | `crypto:close (needs an entity like BTC-USD)` | yes, trade prints are never restated | none |
| **finra-short-volume** | daily short volume and short ratio per symbol | `short:short_ratio (needs an entity)` | yes, published after the close, never revised | none |
| **apewisdom** | retail forum mention ranks across ~15 stock and crypto subreddits No history endpoint upstream. Backtestable history starts the day you record it. | `ape:all-stocks, ape:wallstreetbets, ape:all-crypto` | only forward, known_at is when Vintage fetched it | none |
| **ecb-reference-rates** | daily FX reference rates against the euro, 1999 onward, plus cross rates | `fx:EURUSD, fx:USDJPY` | yes, published each afternoon and never revised | none |
| **cboe-indices** | VIX and the volatility family: term structure, VVIX, SKEW Index levels only. Historical option chains are paid everywhere. | `vol:VIX, vol:VIX3M, vol:SKEW` | yes, index levels are not revised | none |
| **sec-form-25** | every delisting on record: 36,830 filings, 11,614 companies, 2003 on The survivorship correction. Complete from April 2006, partial before. | `delisting:form25` | yes, filing dates, never revised | none |
| **sec-xbrl-frames** | one concept across every filer in one call, the cross-section 6,289 filers in one 840KB request. Use fetch per entity when the date matters. | `frame:us-gaap/Assets/CY2023Q1I` | no, carries the accession but not its filing date | none |
| **us-treasury** | par yield curve, 14 tenors from 1 month to 30 years | `ust:10y, ust:2y, ust:all` | yes, published daily and never revised | none |
| **open-source-asset-pricing-ports** | the monthly long-short return each replicated predictor produced What Chen & Zimmermann got, beside openap: which is what the paper claimed. The series to calibrate an implementation against. | `openapret:Mom12m` | no, the file is rebuilt on each release and old months can change | none |
| **sec-edgar-sic** | the industry a filer files under: SIC code, SEC description, division The label a cross-sectional neutralizer needs. Current only, so group today's cross-section with it rather than backdating it. | `sector:sic, sector:name (needs an entity)` | no, EDGAR states the current code with no date of change | none |
| **cftc-cot** | weekly futures positioning by trader class | `cot:noncommercial_net (needs an entity like SP500)` | yes, Tuesday positions, released Friday, lag preserved | none |
| **sec-form-13f** | institutional equity holdings for every manager over $100m Long US equity only. Values normalised across the 2023 thousands-to-dollars change. | `13f:value, 13f:shares (needs an entity like BERKSHIRE)` | yes, quarter end and filing date, up to 45 days apart | none |
| **bls** | CPI to item level, payrolls, JOLTS, wages, productivity Keyless tier is 25 queries a day. Use fred: when the vintage matters. | `bls:CUUR0000SA0` | no, BLS ships no release date with the value | none |
| **bea** | the national accounts, every line of a NIPA table at once GDP is revised at least three times. ALFRED via fred: has the vintages. | `bea:T10101` | no, current estimate only, never the first print | free key |
| **fred** | 800k macro series, with ALFRED first-release vintages | `fred:CPIAUCSL` | yes, real-time vintages | free key |

## Field prefixes

How a field name routes to a source.

| Prefix | Source | Needs an entity |
|---|---|---|
| `price:` | prices | yes |
| `fred:` | fred | no |
| `french:` | french | no |
| `openap:` | openap | ,  |
| `openapret:` | openap_ports | ,  |
| `ape:` | apewisdom | ,  |
| `crypto:` | crypto | ,  |
| `short:` | finra | ,  |
| `fx:` | ecb | ,  |
| `vol:` | cboe | ,  |
| `delisting:` | delistings | ,  |
| `frame:` | frames | ,  |
| `ust:` | treasury | ,  |
| `cot:` | cftc | ,  |
| `sector:` | sector | ,  |
| `13f:` | thirteenf | ,  |
| `bls:` | bls | ,  |
| `bea:` | bea | ,  |
| `index:` | prices | ,  |
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

Federal Reserve Bank of St. Louis. These are hand-picked so `discover` answers well before a key is configured, but **any** of FRED's 800,000+ series works by id, and ALFRED supplies first-release vintages.

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
CBOE, no key. Index levels are computed from that session's option prices and are not revised. **Levels only**, historical option chains are paid at every vendor and remain a gap.
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
## Institutional holdings
SEC Form 13F. Every manager running over $100m in US equities files a holdings table within 45 days of each quarter end, and that 45-day gap is the point: the positions are dated to the quarter, the document is dated to the day it was accepted, and `as_of` returns the filing that actually existed on a given day.
| Field | Returns |
|---|---|
| `13f:value` | position market value in USD |
| `13f:shares` | position size in shares |

Three things this handles that a naive parse does not. Filings from January 2023 report market value in dollars and everything before reports thousands, with nothing in the document saying which, so a series across the boundary jumps by 1,000x. A manager with sub-advisers files one line per manager per security, so the lines have to be summed rather than counted. And an amendment comes in two kinds: RESTATED replaces the table, NEW HOLDINGS lists only additions, so treating the second as the quarter turns an eleven-name book into one position.
25 managers have shortcuts; any other filer is found by name through EDGAR.
| Shortcut | Filer |
|---|---|
| `BERKSHIRE` | Berkshire Hathaway Inc (CIK 0001067983) |
| `BRIDGEWATER` | Bridgewater Associates, LP (CIK 0001350694) |
| `RENAISSANCE` | Renaissance Technologies LLC (CIK 0001037389) |
| `CITADEL` | Citadel Advisors LLC (CIK 0001423053) |
| `TWOSIGMA` | Two Sigma Investments, LP (CIK 0001179392) |
| `MILLENNIUM` | Millennium Management LLC (CIK 0001273087) |
| `AQR` | AQR Capital Management LLC (CIK 0001167557) |
| `BAUPOST` | Baupost Group LLC/MA (CIK 0001061768) |
| `PERSHING` | Pershing Square Capital Management, L.P. (CIK 0001336528) |
| `TIGERGLOBAL` | Tiger Global Management LLC (CIK 0001167483) |
| `SOROS` | Soros Fund Management LLC (CIK 0001029160) |
| `DESHAW` | D. E. Shaw & Co, L.P. (CIK 0001009268) |
| `ELLIOTT` | Elliott Investment Management L.P. (CIK 0001791786) |
| `APPALOOSA` | Appaloosa LP (CIK 0001656456) |
| `LONEPINE` | Lone Pine Capital LLC (CIK 0001061165) |
| `COATUE` | Coatue Management LLC (CIK 0001135730) |
| `VIKING` | Viking Global Investors LP (CIK 0001103804) |
| `DUQUESNE` | Duquesne Family Office LLC (CIK 0001536411) |
| `GREENLIGHT` | Greenlight Capital Inc (CIK 0001079114) |
| `THIRDPOINT` | Third Point LLC (CIK 0001040273) |
| `SCION` | Scion Asset Management, LLC (CIK 0001649339) |
| `ARK` | ARK Investment Management LLC (CIK 0001697748) |
| `HIMALAYA` | Himalaya Capital Management LLC (CIK 0001709323) |
| `MARSHALLWACE` | Marshall Wace, LLP (CIK 0001318757) |
| `MANGROUP` | Man Group plc (CIK 0001637460) |

13F covers long US equity, ADRs, convertibles and listed options only. Shorts, cash, bonds, commodities and foreign listings are never in it, so this is one side of a book and never the book.
## Macro beyond FRED
Two statistical agencies served directly. Both are breadth rather than vintage: neither ships a release date with the value, so their rows carry no `known_at` and say so. When the backtest needs the number that was actually published at the time, `fred:` with ALFRED vintages is the free answer and these are not.
### Bureau of Labor Statistics (17 shortcuts, no key)
CPI down to item strata, payrolls, JOLTS, wages, productivity. Any BLS series id works, not just these. Keyless requests are capped at 25 a day and 10 years per call; a free key raises that to 500 and 20.
| Field | Series |
|---|---|
| `bls:CUUR0000SA0` | CPI-U, all items, not seasonally adjusted |
| `bls:CUSR0000SA0` | CPI-U, all items, seasonally adjusted |
| `bls:CUSR0000SA0L1E` | Core CPI, less food and energy |
| `bls:CUUR0000SAF1` | CPI, food |
| `bls:CUUR0000SAH1` | CPI, shelter |
| `bls:CUUR0000SETB01` | CPI, gasoline (all types) |
| `bls:WPUFD4` | PPI, final demand |
| `bls:LNS14000000` | Unemployment rate, 16 and over |
| `bls:LNS11300000` | Labor force participation rate |
| `bls:LNS12300060` | Employment-population ratio, 25-54 |
| `bls:CES0000000001` | Total nonfarm payrolls |
| `bls:CES0500000003` | Average hourly earnings, private |
| `bls:CES0500000002` | Average weekly hours, private |
| `bls:JTS000000000000000JOL` | Job openings, total nonfarm (JOLTS) |
| `bls:JTS000000000000000QUR` | Quits rate, total nonfarm (JOLTS) |
| `bls:PRS85006092` | Nonfarm labor productivity, percent change |
| `bls:CIU1010000000000A` | Employment cost index, compensation |

### Bureau of Economic Analysis (11 tables, free key)
One call returns every line of a NIPA table rather than one series, which is the shape a GDP decomposition needs. GDP is published as an advance estimate, revised twice within three months, then again at every annual and benchmark revision, this endpoint serves only the current estimate.
| Field | Table |
|---|---|
| `bea:T10101` | Real GDP, percent change from preceding period |
| `bea:T10102` | Contributions to percent change in real GDP |
| `bea:T10105` | GDP in current dollars, by component |
| `bea:T10106` | Real GDP in chained dollars, by component |
| `bea:T10104` | GDP price indexes, by component |
| `bea:T20100` | Personal income and its disposition |
| `bea:T20600` | Personal income and outlays, monthly |
| `bea:T20804` | Real PCE price index, by type of product |
| `bea:T50100` | Saving and investment |
| `bea:T30100` | Government current receipts and expenditures |
| `bea:T40100` | Foreign transactions |

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

FINRA, published after each close and never revised. This is **short volume, not short interest**, shares sold short during the session, including market-maker hedging that is flat again by the close. A flow measure, not outstanding bearish positioning.

| Field | Returns |
|---|---|
| `short:short_ratio` | short volume as a share of total reported volume |
| `short:short_volume` | shares sold short |
| `short:exempt_volume` | short-exempt shares |
| `short:total_volume` | total reported volume |

One HTTP request per trading day, so `days` defaults to 20 and caps at 90.

## Forum sentiment (7 scopes)

ApeWisdom. No key. **No history endpoint upstream**. Every row is stamped `known_at` = the moment Vintage fetched it, so backtestable history begins the day you start recording. Vendors selling years of "historical sentiment" built it by re-scoring archived posts with a model that already knew what happened next.

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

Every concept every US filer has tagged is reachable. There is no fixed list, because the
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

Costs are charged on turnover on every run. There is no zero-cost mode. Returns are computed over 252 trading days per year.
---

Counts and coverage spans measured at generation time. Vintage redistributes none of this data; each upstream source keeps its own terms.
