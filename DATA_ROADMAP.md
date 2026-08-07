# Data Roadmap

What Vintage should add next to become the most complete *honest* market-data
aggregator that costs $0. Every candidate below is judged against
[PRINCIPLES.md](PRINCIPLES.md), chiefly rule 1 (fetchable by a stranger) and
rule 2 (an honest `known_at`, or `UNKNOWN_VINTAGE`).

Endpoint reachability was probed on **2026-08-06** with a plain `curl` and no
credentials. Status codes are recorded per row; they are evidence the source is
live and keyless, not a guarantee of terms.

---

## 0. The admission rule, restated

A source gets in when all four hold:

1. **Fetchable.** Public HTTP, no login, no paid tier for the base data.
2. **Dated.** It tells us when each value became public, or we can observe that
   moment ourselves and say so.
3. **Not resold.** Prefer the body that files, publishes, or computes it.
4. **Zero new tools.** It arrives as a prefix behind `fetch`/`discover`.

Anything failing (2) is not rejected. It is admitted *labelled*. ApeWisdom is
already the precedent: no upstream history, so every row is stamped with the
moment we fetched it.

---

## 1. The archive layer, the biggest missing capability

This is the one addition that changes what Vintage can answer, not just how much
it covers. It fixes **survivorship and membership**, the two drift modes the
landing page names but the code cannot currently repair.

### 1.1 Wayback Machine CDX API, `wayback:`

`https://web.archive.org/cdx/search/cdx?url=...&output=json`, **verified 200**,
returns `timestamp, original, statuscode, digest, length` per capture.

Confirmed live example: the S&P 500 constituent list page has a capture at
`20051208040053`. That single row is a point-in-time index membership snapshot
from December 2005, free, with a real timestamp.

What it unlocks:

| Question Vintage cannot answer today | Archive answer |
|---|---|
| Who was in the S&P 500 on 2005-12-08? | Wikipedia constituent page, that capture |
| Was this ticker listed in 2011? | Company IR / exchange listing page captures |
| What did this ETF hold in 2016? | Issuer holdings page captures |
| What did the company say before it deleted it? | Any captured page, by `digest` change |

**`known_at` semantics. The honest part.** An archive proves a page was public
*by* the capture time, not *at* it. Crawl lag is real and variable. So the
archive layer must emit an upper bound, not a date:

- `known_at` = capture timestamp
- `known_at_is_upper_bound` = `true`
- `vintage` = `"archive-observed"`
- `known_at_lower_bound` = previous capture with a *different* `digest`

The interval between two captures with different digests is the honest window in
which the change became public. That interval is data, and Vintage should return
it rather than collapse it to a single date. Nothing else in the stack does this.

**Gotchas.** Rate limits are aggressive (we hit `429` twice during probing).
Needs backoff, caching, and a polite UA. Coverage is uneven before ~2005 and for
low-traffic pages. Robots-era exclusions removed some captures retroactively.

### 1.2 Common Crawl index, `cc:`

`https://index.commoncrawl.org/collinfo.json`: **verified 200**. ~100 crawls,
each a named corpus with a fixed crawl window, addressable by URL prefix through
the CDX-style index, with the payload in S3 WARC ranges.

Weaker than Wayback for a single URL over time; far stronger for *corpus at a
date*: every retail product page in a crawl window, every filing-adjacent news
page. The crawl window is a genuine `known_at` bracket, already published.

Use it for breadth (what existed across a sector at date T), Wayback for depth
(one URL's full history).

### 1.3 What archives will not fix

Tweets. There is no free X/Twitter API, Wayback's tweet coverage is incidental,
and every vendor selling "years of historical sentiment" built it by re-scoring
old posts today: which is a look-ahead machine wearing a timestamp. The only
honest sentiment history is one you start recording. Vintage already does this
correctly with ApeWisdom; StockTwits (`api.stocktwits.com`, **verified 200**,
keyless) can join on identical terms: live-only, stamped at fetch, never
backfilled.

---

## 2. Tier 1, add next, high value, verified free

Ordered by research value per unit of work.

### CFTC Commitments of Traders, `cot:`
`publicreporting.cftc.gov/resource/6dca-aqww.json`, **200**, Socrata, keyless.
Weekly positioning by trader class across every futures market, published Friday
for Tuesday, **never revised**. Real `observed_at` (Tuesday) and real `known_at`
(Friday 15:30 ET). One of the cleanest point-in-time datasets in existence, and
the standard input for a whole literature on commodity and FX positioning.

### SEC Fails-to-Deliver, `ftd:`
`sec.gov/data-research/sec-markets-data/fails-deliver-data`, **200**. Semi-
monthly CSVs, settlement fails per CUSIP. Pairs with the FINRA short volume
already wired to give a squeeze/constraint picture nobody assembles for free.
Publication date is stated; never revised.

### Wikipedia pageviews, `wiki:`
`wikimedia.org/api/rest_v1/metrics/pageviews/...`, **200**, keyless, daily and
hourly, back to 2015. Genuine retail-attention proxy that is *not* re-scored:
the count for 2020-01-02 is fixed forever. Strictly more honest than Google
Trends, which normalizes and re-baselines on every query, Trends should be
**rejected** for exactly that reason.

### Congressional trading disclosures, `congress:`
`disclosures-clerk.house.gov` (**200**; Senate eFD) **302** (form-gated, still
public). Periodic transaction reports carry both the trade date and the
disclosure date, i.e. `observed_at` and `known_at` are printed on the document.
A widely-followed signal that no free API packages with honest dating.

### GDELT 2.0, `gdelt:`
`api.gdeltproject.org/api/v2/doc/doc`: **200** (429s under load; back off).
Global news, 15-minute cadence, since 2015, with per-article publication
timestamps and tone/theme codes. This is the honest replacement for "news
sentiment history". The article timestamp is the source's own.

### Federal Register, `fedreg:`
`federalregister.gov/api/v1/documents.json`: **200**. Rules, proposed rules,
notices, with publication dates and agency. Regulatory-event studies become
possible; the date *is* the point.

### Treasury FiscalData, `treasury:`
`api.fiscaldata.treasury.gov/...`: **200**, keyless, versioned, paginated.
Daily Treasury statement, auctions, average interest rates, debt outstanding.
Primary source, first-release dated.

### NY Fed Markets API, `nyfed:`
`markets.newyorkfed.org/api/rates/secured/sofr/last/2.json`, **200**. SOFR and
reference rates, repo operations, primary dealer positions, from the desk that
runs them, published same day, revised only with a marked revision flag.

---

## 3. Tier 2, worth adding, smaller or narrower

| Source | Prefix | Probe | What it adds |
|---|---|---|---|
| SEC 13F / N-PORT / N-CEN | `sec:` (extend) | 200 (EDGAR) | Institutional and fund holdings, with filing dates, the honest ownership panel |
| CBOE daily index files | `cboe:` | 200 | VIX history, put/call ratios, index settlement, free CSVs |
| DefiLlama | `defi:` | 200 | Protocol/chain TVL history, keyless, the crypto fundamentals layer Coinbase prices lack |
| USAspending | `gov:` | 200 | Federal contract awards by recipient, with award dates, genuinely predictive for defense/health names |
| Japan EDINET | `edinet:` | 200 | Japanese filings API, keyless, dated, the first non-US filing stream |
| ESMA registers | `esma:` | 200 | EU net short positions, the European counterpart to FINRA short volume |
| OpenFIGI | resolver | 405 (POST-only, works) | Identifier mapping: FIGI ↔ ticker ↔ ISIN, improves `resolve` beyond US filers |
| Frankfurter / ECB FX | `fx:` | 301→200 | ECB daily reference rates back to 1999, keyless, non-USD backtests |
| alternative.me Fear & Greed | `fng:` | 200 | Crypto sentiment index, daily, fixed history |
| USDA NASS / EIA | `usda:` `eia:` | 401 (free key) | Crop and energy fundamentals, free but keyed, so gated behind rule 1's spirit: optional prefix, absent without a key |

---

## 4. Explicit rejections, and why

Recording these matters as much as the additions. They are the rule doing work.

- **Google Trends.** Re-normalized per query and per sample. Two pulls of the
  same date disagree. Fails rule 2 irreparably.
- **Purchased "historical sentiment".** Built by re-scoring old text with
  today's model. A look-ahead machine with a timestamp column.
- **IBES / analyst estimates.** No free source with honest first-release dates.
  Real gap; state it in `discover` rather than fake it.
- **Residential proxy networks (Massive et al.).** Solves *reach*, not *time*.
  A proxy fetches today's page from a different IP; it carries no `known_at` at
  all. Orthogonal to this project. The archive layer is the correct answer to
  the same instinct.
- **Scraped aggregator sites.** Rule 3. If the regulator publishes it, take it
  from the regulator.

---

## 5. Suggested order of work

1. **Wayback CDX adapter** with the upper-bound `known_at` contract, plus the
   S&P 500 membership history built on it. This retires the survivorship
   warning the response currently has to print.
2. **CFTC COT**, cheapest clean win, textbook point-in-time.
3. **Wikipedia pageviews + GDELT**, the attention/news pair, both honestly
   dated, which together replace the sentiment products we cannot buy.
4. **SEC FTD + 13F/N-PORT**, deepens the source already best understood.
5. **Common Crawl**, after Wayback, reusing the same archive contract.
6. Tier 2 opportunistically; each is a registry entry, not a tool.

Every step above is a new prefix behind the same six verbs. Rule 6 holds: the
tool count stays at six no matter how far this list runs.

---

## Verified-live candidates, open for contribution

Probed 2026-08-07. Each returned a real payload, not a landing page. Sizes are
what the endpoint actually served.

### Robert Shiller's long-run series, `shiller:`

`http://www.econ.yale.edu/~shiller/data/ie_data.xls`, **200, 1.6 MB.**

Monthly S&P price, dividends, earnings, CPI and the long rate **back to 1871**,
plus CAPE. This is the single biggest history extension available to us: Ken
French starts in July 1926 and this reaches fifty-five years further. Yale
publishes it, so it satisfies the not-resold rule.

Vintage on point-in-time: it does not have any. Shiller reconstructs the early
series from historical sources, so it is `UNKNOWN_VINTAGE` and must say so. It
is for describing regimes a century back, not for backtesting into them.

### Welch-Goyal predictors, `wg:`

Google Sheets export, **200, 475 KB.**

The standard equity-premium predictability dataset: dividend and earnings
yields, book to market, default and term spreads, bill rate, net issuance,
inflation, monthly from 1871. Essentially every return-predictability paper of
the last twenty years is scored against it.

It is embarrassing that this is not already wired up. The first Alpha Archive
replication had to fetch it by hand, which is exactly the glue Vintage exists
to remove.

### Economic Policy Uncertainty, `epu:`

`https://www.policyuncertainty.com/media/All_Daily_Policy_Data.csv`, **200, 249 KB.**

Baker, Bloom and Davis. Daily since 1985, built from newspaper coverage.

Worth contrasting with ApeWisdom, which has no history at all and is stamped
forward-only. EPU is the opposite: decades of it, computed once from an archive
that does not move. It is the sentiment series a backtest can actually use, with
the honest caveat that the index was constructed after the fact.

### SEC financial statement data sets, `fsds:`

`https://www.sec.gov/files/dera/data/financial-statement-data-sets/{year}q{q}.zip`,
**200, 124 MB per quarter.**

Every number from every XBRL filing in a quarter, as flat tables, with the
filing date attached. This is the bulk complement to `frame:`, which serves one
concept across all filers but carries no `known_at`. These files do carry it,
which would close the one honest gap in the frames source.

Large, so it wants the streaming treatment `delistings.py` already uses.

### Damodaran datasets, `nyu:`

`https://pages.stern.nyu.edu/~adamodar/pc/datasets/histimpl.xls`, **200, 113 KB.**

Implied equity risk premium by year, plus industry betas, costs of capital and
margins. NYU publishes it. Useful as a denominator: a strategy's excess return
means more against a contemporaneous ERP than against zero.

### Probed and not yet viable

| Source | What happened |
|---|---|
| AAII sentiment survey | 403, blocked to programmatic access |
| EIA open data | 403, needs a free key, so it is a `key_required` source |
| SEC N-PORT fund holdings | 404 at the guessed path, the dataset exists and the URL needs finding |
| SEC fails-to-deliver | 404 at the guessed path, same |

The last two are worth someone's afternoon. N-PORT is monthly ETF and mutual
fund holdings, free, from the regulator, which would be the second holdings
source after 13F and the only one covering funds rather than managers.
