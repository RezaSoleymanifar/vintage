# Integrations

Vintage is a data layer. It has no backtester and no broker, and it should not
grow either: rule 6 caps the tool count at six. What it *can* do is feed the
engines people already run.

This file is a brief for two of those, written so a contributor can pick either
one up without asking anything first. Both are adapters that live outside the
core: they import Vintage, they are not imported by it.

Neither requires anyone's permission. That is the point of choosing these two.

---

## 1. QuantConnect / LEAN, `adapters/lean`

### What LEAN is

[LEAN](https://github.com/QuantConnect/Lean) is QuantConnect's backtesting and
live-trading engine, Apache 2.0, runnable on your own machine with the `lean`
CLI. QuantConnect the company sells hosted compute and data on top of it. The
engine itself is free and does not phone home.

### Why LEAN and not the company

Three reasons, in order of weight.

**Local LEAN is data-starved.** A stranger who `pip install lean` and runs a
backtest gets the sample data QuantConnect ships and little else. Everything
past that is a cloud subscription or a manual download into LEAN's on-disk
format. This is the single most common complaint in their forum, and it is
exactly the gap Vintage fills for free.

**Custom data is a first-class, documented API, not a hack.** You subclass
`PythonData`, implement `GetSource` and `Reader`, and `AddData` in `Initialize`.
The engine then streams your rows through the same pipeline as its own equity
bars: same warm-up, same slice, same order handling. There is no fork, no patch,
no vendored build.

**The point-in-time semantics already match.** LEAN's entire design is that a
row is delivered to the algorithm at the timestamp it became knowable, never
before. That is `known_at` under a different name. Most data adapters have to
paper over an impedance mismatch here; this one does not. A Vintage envelope
carries the field LEAN wants, already correct.

The corollary is the honest part: where Vintage stamps `UNKNOWN_VINTAGE` or
`known_at_is_upper_bound`, the adapter must refuse to smuggle the row in at an
optimistic time. Deliver it at the upper bound, or do not deliver it. An adapter
that quietly shifts a timestamp earlier turns a look-ahead-safe engine into a
look-ahead machine, and the user never sees it happen.

### Scope of the work

| Piece | Sketch |
|---|---|
| `VintageData(PythonData)` | `GetSource` returns a `SubscriptionDataSource` pointing at a locally materialised CSV; `Reader` parses one row |
| Materialiser | `vintage fetch <prefix>` → LEAN's expected on-disk layout, run once before the backtest |
| Timestamp rule | `Time` = `known_at`. Upper-bound rows delivered at the bound. `UNKNOWN_VINTAGE` rows dropped by default, admitted only behind an explicit flag |
| Example algorithm | One runnable strategy that is *not* a price strategy, short volume or forum mentions, something LEAN users cannot get anywhere else free |
| README | Copy-pasteable: install, materialise, `lean backtest` |

Roughly 150 lines for the data type, plus the materialiser. The example
algorithm matters more than either, see distribution below.

### Where this ends up

The [Dataset Market](https://www.quantconnect.com/datasets) is QuantConnect's
in-product catalogue of third-party data. Getting listed puts Vintage in front
of every hosted user without them installing anything. That is the endgame, and
it is a conversation worth having, but from a position where the adapter
already exists and has users, not as a cold pitch. Ship first, list second.

---

## 2. Alpaca, `adapters/alpaca`

### What Alpaca is

A US brokerage with an API-first product: REST and WebSocket endpoints for
placing orders, plus market data (free IEX tier, paid SIP). Popular with people
who write their own execution code rather than use a platform.

### Why they are the warmer lead

Alpaca sells execution. They do not sell alternative data and show no sign of
wanting to build it. Their community asks for sentiment, short volume, and
fundamentals constantly, and the honest answer today is "go buy it."

Vintage is a better answer that costs Alpaca nothing to give. A free MCP server
that makes their API more useful is pure upside for them, no build, no support
burden, no cannibalised revenue. That asymmetry is why this one is worth an
actual email, and QuantConnect is not.

### Scope of the work

| Piece | Sketch |
|---|---|
| `alpaca:` source | Register the free IEX bars endpoint as one more prefix behind `fetch`/`discover`. Keyed, so absent without credentials, same treatment as USDA/EIA in the roadmap |
| Position-aware example | A script that reads current Alpaca positions and enriches each with Vintage context: short volume, forum mentions, filing dates |
| Honest boundary | Vintage does not place orders and must not. The adapter reads; execution stays in the user's code |

Note the direction of the dependency: Alpaca is the *broker*, so the interesting
artifact is Vintage feeding an Alpaca-executed strategy, not Alpaca feeding
Vintage. The `alpaca:` price source is a nice-to-have; the enrichment example is
the thing.

---

## 3. Distribution, how anyone finds out

This is the part that decides whether either adapter matters, and it is worth
being blunt about.

**Nobody adopts a data adapter. People adopt a backtest that runs.** A
repository called `vintage-lean` with a clean API and no example gets stars and
no users. A single file that someone can paste into LEAN and watch produce an
equity curve using data they could not previously get for free, that is the
unit that travels. Build the adapter for correctness; build the example for
distribution. They are different artifacts with different jobs.

The channels, ranked by how much intent the reader arrives with:

| Channel | Why it works | What to post |
|---|---|---|
| **QuantConnect forum** | People post "how do I get X into LEAN" as a literal recurring thread. Highest intent per reader on the internet for this specific thing. | Answer real threads with a working algorithm, not a link |
| **PyPI + a short name** | `pip install vintage-lean` is the whole install story. Discoverability is low but conversion is total | Package, with the example in the README |
| **LEAN's own docs and repo** | QuantConnect's custom-data documentation and the community examples are read by everyone who hits the wall | A PR or a documented example, upstream where possible |
| **r/algotrading, r/quant** | Wide, low intent, spiky. Works once with a genuinely novel artifact, never twice with the same one | The chart, not the repo. Lead with a finding |
| **Dataset Market listing** | In-product, permanent, zero ongoing effort | Apply after the adapter has users |
| **Alpaca community / integrations page** | Smaller, but Alpaca actively wants third-party integrations listed | The enrichment example |

Two failure modes worth naming, because both are the default:

- **Leading with the abstraction.** "A point-in-time data layer with an honest
  `known_at` contract" is true and lands with nobody. "Here is a backtest of
  Reddit mention momentum, free, runs locally in LEAN" is the same project
  described by its output.
- **Posting once.** The forum answer is not a launch, it is a habit. The
  adapter's user count is roughly the number of real questions it has answered.

The through-line for both integrations: the adapter earns the right to the
listing, the listing does not create the users.

---

## 4. Status

Neither adapter is built. Both are open for contribution. Constraints that hold
regardless of who writes them:

1. Adapters live outside `src/vintage/`. Vintage does not import LEAN or Alpaca.
2. No new tools. Anything an adapter needs from Vintage arrives through the
   existing six verbs, or it is a registry entry, see [`PRINCIPLES.md`](PRINCIPLES.md).
3. A timestamp is never made earlier than the envelope says. Upper bounds stay
   upper bounds all the way into the engine.
