"""Point-in-time price reconstruction.

The bug this suite exists to prevent: Yahoo's `quote.close` looks like a raw
print and is not — it is already split-adjusted. Building a point-in-time
series on top of it silently reintroduces the retroactive adjustment the whole
exercise is meant to remove, and the result looks plausible, which is worse.
"""

import pytest

from vintage import envelope, pit


def closes(**over):
    base = {
        "2009-12-30": 100.0,
        "2009-12-31": 100.0,
        "2014-06-08": 700.0,
        "2014-06-10": 100.0,
        "2020-09-01": 100.0,
    }
    base.update(over)
    return base


SPLIT_7 = {"date": "2014-06-09", "kind": "split", "ratio": 7.0, "label": "7:1"}
SPLIT_4 = {"date": "2020-08-31", "kind": "split", "ratio": 4.0, "label": "4:1"}
DIV = {"date": "2013-01-10", "kind": "dividend", "amount": 5.0, "label": "5.0"}


# --------------------------------------------------------------- unadjusting


def test_unadjust_restores_the_printed_price():
    """A feed close of 7.53 with a 7:1 and a 4:1 still ahead printed at 210.84."""
    out = pit.unadjust({"2009-12-31": 7.53}, [SPLIT_7, SPLIT_4])
    assert out["2009-12-31"] == pytest.approx(7.53 * 28, rel=1e-9)


def test_unadjust_ignores_splits_before_the_bar():
    out = pit.unadjust({"2021-01-04": 100.0}, [SPLIT_7, SPLIT_4])
    assert out["2021-01-04"] == pytest.approx(100.0)


def test_unadjust_without_splits_changes_nothing():
    data = {"2020-01-01": 12.5}
    assert pit.unadjust(data, [DIV]) == data


# ----------------------------------------------------------------- adjusting


def test_as_of_excludes_actions_that_had_not_happened():
    """The whole point. In 2010 the 2014 split was not knowable."""
    raw = {"2009-12-31": 210.0}
    early = pit.adjust(raw, [SPLIT_7, SPLIT_4], as_of="2010-01-01")
    late = pit.adjust(raw, [SPLIT_7, SPLIT_4], as_of="2021-01-01")
    assert early["2009-12-31"] == pytest.approx(210.0)
    assert late["2009-12-31"] == pytest.approx(210.0 / 28)


def test_no_as_of_applies_every_action():
    out = pit.adjust({"2009-12-31": 210.0}, [SPLIT_7, SPLIT_4])
    assert out["2009-12-31"] == pytest.approx(210.0 / 28)


def test_a_split_does_not_adjust_prices_after_it():
    out = pit.adjust({"2014-06-10": 100.0}, [SPLIT_7])
    assert out["2014-06-10"] == pytest.approx(100.0)


def test_dividend_uses_the_close_before_the_ex_date():
    raw = {"2013-01-09": 100.0, "2013-01-11": 95.0}
    out = pit.adjust(raw, [DIV])
    assert out["2013-01-09"] == pytest.approx(95.0)     # 100 * (1 - 5/100)
    assert out["2013-01-11"] == pytest.approx(95.0)     # after the ex-date


def test_adjusting_nothing_returns_nothing():
    assert pit.adjust({}, [SPLIT_7]) == {}


# --------------------------------------------------------------------- rows


def test_rows_are_marked_as_filed_not_retroactive():
    """Once the level no longer depends on later information, that is true."""
    out = pit.rows("AAPL", closes(), [SPLIT_7, SPLIT_4], as_of="2010-01-01")
    assert out
    assert all(r["vintage"] == envelope.AS_FILED for r in out)
    assert all(r["known_at"] == r["observed_at"] for r in out)


def test_rows_report_how_many_actions_were_in_scope():
    out = pit.rows("AAPL", closes(), [SPLIT_7, SPLIT_4, DIV], as_of="2015-01-01")
    assert out[0]["actions_known"] == 3
    assert out[0]["actions_applied"] == 2          # the 2020 split is excluded


def test_warning_names_the_splits_it_left_out():
    note = pit.warnings_for([SPLIT_7, SPLIT_4], "2010-01-01")
    assert note and "7:1" in note[0] and "4:1" in note[0]


def test_no_warning_when_nothing_was_excluded():
    assert pit.warnings_for([SPLIT_7], "2021-01-01") == []
    assert pit.warnings_for([SPLIT_7], None) == []


def test_actions_parses_splits_and_dividends():
    parsed = pit.actions({"events": {
        "splits": {"1": {"date": 1402272000, "numerator": 7, "denominator": 1,
                         "splitRatio": "7:1"}},
        "dividends": {"2": {"date": 1357776000, "amount": 5.0}},
    }})
    assert [e["kind"] for e in parsed] == ["dividend", "split"]   # sorted by date
    assert parsed[1]["ratio"] == pytest.approx(7.0)


def test_actions_skips_malformed_entries():
    parsed = pit.actions({"events": {
        "splits": {"1": {"date": 1402272000, "numerator": 0, "denominator": 1}},
        "dividends": {"2": {"date": 1357776000}},
    }})
    assert parsed == []


@pytest.mark.network
def test_apple_2009_close_matches_the_historical_record():
    """210.73 is what actually printed. Any adjustment leaking in breaks this."""
    import asyncio

    from vintage.sources import yahoo

    rows = asyncio.run(yahoo.pit_prices("AAPL", as_of="2010-01-01"))
    by = {r["observed_at"]: r["value"] for r in rows}
    assert by["2009-12-31"] == pytest.approx(210.73, abs=0.05)
