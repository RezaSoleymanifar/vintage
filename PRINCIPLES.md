# Principles

Short list. These are the rules that decide arguments, not aspirations.

## 1. If Vintage cannot fetch it over the internet, it does not exist

No adapter, no fixture, no test, and no downstream project may depend on a file
that lives only on one machine. Not a parquet dump, not a CSV someone downloaded,
not a database seeded by hand.

The test is blunt: **a stranger who runs `uvx vintage-mcp` must be able to
reproduce every result we publish.** If they cannot, the result is a claim rather
than a finding, and claims are what this project exists to check.

This rule has teeth. It has already cost us:

- Alpha Archive's price and fundamentals loaders read a parquet from a private
  sibling repo. That made "open, verified, crowdsourced" untrue, and is why the
  data layer is being replaced with Vintage.
- OpenAP's SignalDoc was a local CSV copy. Rather than delete it, we made it
  legitimate. It is now fetched from the public upstream, so anyone gets the
  same 331 rows.

Local copies are allowed only as a *cache* of something fetchable, never as the
source of truth.

## 2. Two dates, or say you do not know

Every value carries `observed_at` and `known_at`. A source that cannot supply an
honest `known_at` gets `UNKNOWN_VINTAGE` and a null, never an invented date, and
never a silent default to today.

## 3. The panel enforces point-in-time, not the caller

Look-ahead prevention is structural: the backtest panel is indexed on `known_at`,
so any slice of it is automatically point-in-time. There is no flag to disable
this, because a flag is a thing people set to zero at 2am.

## 4. Costs are always on

There is no zero-cost mode. A zero-cost backtest is not a backtest.

## 5. The trial counter is not optional

Every backtest deflates its Sharpe by how many specifications were tried. A user
cannot turn this off, and no feature may be built that optimizes toward a higher
Sharpe. That would be building the disease and the cure in one package.

Honesty outputs (deflated Sharpe, warnings, verdicts, vintage flags) are
constants. They are never tuned, never softened, and never learned from user
behaviour, even when softening them would measurably improve engagement.

## 6. Source is a parameter, never a tool

Twenty more sources must add zero tools. Breadth arrives through `discover`, not
through a longer tool list the model has to read.

## 7. Say what is missing, in the response

Known gaps belong in the payload the model reads, not only in the README. A
survivorship warning the user never sees is not a warning.

## 8. Claims get citations, and citations are not endorsements

We implement published methods and name them. Naming an author is not a claim
that they are affiliated with this project, and anything unimplemented is marked
planned rather than described in the present tense.
