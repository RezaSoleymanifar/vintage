# Free data landscape for quants

Every source here is free and machine-accessible. We do not host any of it — the server connects, normalizes, and preserves vintage. Ranked by value-per-unit-of-glue.

Legend — **Key**: none / free key / unofficial. **PIT**: does the source preserve what was known at the time?

---

## Tier 0 — build these first (highest value, nobody has glued them)

| Source | What you get | Key | PIT | Why it matters |
|---|---|---|---|---|
| **SEC EDGAR XBRL** ✅ done | All US filer fundamentals, `filed` dates, restatements | none | ✅ native | The only free point-in-time fundamentals that exist |
| **SEC `frames` API** | One concept, *all companies*, one period — cross-section in a single call | none | ✅ | Turns EDGAR from company-lookup into a factor engine |
| **Open Source Asset Pricing** (Chen–Zimmermann) | 200+ published anomaly signals, reproduced, with code | none | ✅ | Ground truth for the whole "verify published claims" thesis |
| **Ken French Data Library** | FF3/FF5, UMD, industry portfolios, breakpoints, international | none | ✅ | The benchmark every factor claim is scored against |
| **JKP Global Factor Data** (Jensen–Kelly–Pedersen) | 150+ factors, 93 countries, cluster-level | free key | ✅ | Out-of-sample test bed the free world has no access to otherwise |
| **FRED** (St. Louis Fed) | 800k+ macro series — rates, inflation, credit, sentiment | free key | ✅ **vintages via ALFRED** | ALFRED gives real-time macro vintages. Almost nobody uses this and almost everyone should |
| **FINRA short sale volume** | Daily short volume by symbol, per venue | none | ✅ | Free, daily, genuinely predictive, painfully unglued |
| **CFTC Commitments of Traders** | Weekly futures positioning by trader class | none | ✅ | The classic free positioning dataset |

## Tier 1 — prices and the survivorship problem

| Source | What you get | Key | Notes |
|---|---|---|---|
| **Stooq** | Daily OHLCV, global equities/FX/indices, plain CSV | none | No auth, no rate drama. Underrated |
| **Yahoo Finance** | OHLCV, splits, dividends, adj close | unofficial | Grey terms, fragile, everyone uses it. Support it, warn about it |
| **SEC Form 25 / EDGAR** | Delisting events | none | **This is how you fix survivorship bias for free.** Painful, which is the point |
| **SEC `company_tickers_exchange`** + former names | Listing venue, name history | none | Needed to follow tickers through renames |
| **Nasdaq / Tiingo / Alpha Vantage / Twelve Data / FMP / Polygon** | Free tiers, EOD | free key | Thin quotas; useful as fallbacks, not a spine |
| **Crypto exchange APIs** (Binance, Coinbase, Kraken, OKX, Bybit) | Full OHLCV, trades, funding, open interest, deep history | none | The only asset class where retail gets institutional-grade free data |

## Tier 2 — positioning, ownership, flows

| Source | What you get | Key |
|---|---|---|
| **13F filings** | Institutional equity holdings, quarterly | none |
| **Form 4** | Insider buys/sells, with transaction dates | none |
| **13D/G** | Activist and >5% stakes | none |
| **N-PORT** | Mutual fund and ETF holdings, monthly | none |
| **ETF issuer files** (iShares, SPDR, Invesco) | Daily holdings CSVs, straight from the issuer | none |
| **FINRA short interest** | Bi-monthly short interest by symbol | none |
| **NY Fed** | SOFR, EFFR, repo, primary dealer positions | none |

## Tier 3 — macro and rates beyond FRED

| Source | What you get | Key |
|---|---|---|
| **Treasury fiscaldata** | Par yield curve, auctions, debt outstanding | none |
| **BLS** | CPI, PPI, employment, JOLTS | free key |
| **BEA** | GDP, NIPA, trade | free key |
| **Census** | Retail sales, housing, trade | free key |
| **EIA** | Energy production, inventories, prices | free key |
| **USDA NASS** | Agricultural production and stocks | free key |
| **World Bank / IMF / OECD / BIS / ECB / BoE** | Global macro and cross-country panels | none |
| **NOAA** | Weather — real input for ag and energy | none |

## Tier 4 — text and alternative

| Source | What you get | Key | Honest read |
|---|---|---|---|
| **SEC full-text search** (`efts.sec.gov`) | Search the text of every filing since 2001 | none | Underused. Language-change signals live here |
| **Fed communications** | FOMC statements, minutes, speeches, dot plots | none | Clean corpus, timestamped, tone-scorable |
| **USPTO PatentsView** | Patents by assignee, citations, classes | free key | Innovation factors, mappable to CIK with work |
| **USAspending** | Federal contract awards by vendor | none | Direct revenue-exposure signal |
| **FDA** | Drug approvals, trials, adverse events | none | Biotech event studies |
| **GDELT** | Global news events and tone, 2015→ | none | Enormous, noisy, free |
| **Wikipedia pageviews** | Daily attention per entity | none | Cleanest free attention proxy that exists |
| **arXiv q-fin / RePEc** | New quant papers, daily | none | Feeds `paper-to-spec` directly |
| **DOL H-1B/LCA** | Employer filings — hiring proxy | none | Slow, quarterly, real |

## Tier 4b — news and disclosure flow

News is information, and for quants the valuable part is not the prose — it is the **timestamp** and the **entity link**. Anything that gives you "this company, this fact, this minute" is tradeable input. Anything that gives you a headline with no reliable time is decoration.

Build on sources that are free *forever*, not on free tiers that throttle you into uselessness.

| Source | What you get | Key | Timestamp quality |
|---|---|---|---|
| **SEC 8-K** (EDGAR RSS, real time) | Material corporate events, filed to the minute | none | ✅ Exact, legally mandated |
| **EDGAR full-index + RSS** | Every filing as it lands, all filers | none | ✅ Exact |
| **GDELT 2.0** | Global news events, tone, actors, every 15 min since 2015 | none | ✅ Good |
| **Company IR press releases** (RSS/Atom) | Primary-source announcements, pre-spin | none | ✅ Exact |
| **Federal Reserve / FOMC / regional Fed RSS** | Statements, minutes, speeches, H.4.1 | none | ✅ Exact |
| **Central bank feeds** (ECB, BoE, BoJ, BoC) | Policy statements and speeches | none | ✅ Exact |
| **Treasury / BLS / BEA / Census release calendars** | Scheduled macro release times | none | ✅ Exact — lets you separate scheduled from surprise |
| **Wire and outlet RSS** (Reuters, AP, CNBC, Yahoo, Bloomberg headlines) | Headlines and links, unlimited | none | ⚠️ Publication time only |
| **Regulatory feeds** (FDA, FTC, DOJ, EPA, CFTC, FINRA actions) | Approvals, enforcement, recalls | none | ✅ Exact |
| **Nasdaq / NYSE notices** | Halts, delistings, listing deficiencies | none | ✅ Exact |
| **Wikipedia recent changes + pageviews** | Attention spikes per entity, per hour | none | ✅ Exact |
| **Google Trends** (`pytrends`) | Search interest, weekly/daily | unofficial | ⚠️ Rescaled, grey terms |

Deliberately excluded: NewsAPI, Marketaux, Finnhub news, and similar. Their free tiers cap at ~100 calls/day, delay results 24h, forbid production use, or all three. You cannot build a habit on a quota that small — and their paid tiers are the business you would be advertising for.

**The real news product**: an event stream keyed to the identifier spine, where an 8-K, an FDA approval, a halt notice, and a pageview spike for the same company all line up on one timeline with exact times. Nobody does that for free.

## Tier 5 — identifiers (the unglamorous spine)

| Source | What you get | Key | Why |
|---|---|---|---|
| **OpenFIGI** (Bloomberg) | Ticker ↔ FIGI ↔ exchange, free API | free key | The only free global security identifier |
| **GLEIF** | LEI, legal entity hierarchies, full bulk download | none | Parent/subsidiary structure for free |
| **SEC CIK map** ✅ done | Ticker ↔ CIK ↔ name | none | US filer spine |
| **exchange_calendars** | Trading sessions and holidays, global | none | Every alignment bug traces back to this |

CUSIP and SEDOL are licensed. Not available, do not pretend otherwise.

---

## The honest gaps

Free data cannot give you these. Say so plainly rather than shipping a bad substitute:

- **Analyst estimates and revisions** — all paid (I/B/E/S, Refinitiv). No free equivalent.
- **Historical options chains** — surfaces and greeks are paid. Only CBOE summary stats and VIX history are free.
- **Intraday tick and full order book for equities** — free tiers give minute bars at best. Crypto is the exception.
- **Point-in-time index membership** — S&P and MSCI license it. Reconstructing it from filings is possible and horrible.
- **Clean corporate action history pre-2000** — patchy everywhere free.
- **Earnings call transcripts** — mostly paid.

---

## What makes this an engineering feat, not a scraper

Anyone can wrap one API. The work is the layer that makes twenty sources behave like one:

1. **One identifier spine.** CIK, ticker, FIGI, LEI, and exchange all resolved through a single mapping, with name and ticker changes tracked through time.
2. **One time convention.** Every series carries `observed_at` (when the value refers to) and `known_at` (when you could have seen it). Sources that lack the second get an explicit `UNKNOWN_VINTAGE` flag rather than a silent guess.
3. **One shape.** Every response is the same envelope regardless of whether it came from EDGAR XBRL, a French ZIP, a FRED JSON, or a CFTC fixed-width text file.
4. **Rate-limit and cache discipline** per source, so a user cannot get themselves banned.
5. **Calendar alignment.** Trading days, fiscal calendars, and macro release dates reconciled — not resampled and hoped for.
6. **Provenance on every field.** Source URL and retrieval time attached, always. Same discipline as `paper-to-spec`: cite everything, flag what is unknown.

That layer is worth more than any single feed, and it is exactly what nobody does for free.
