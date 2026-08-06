"""The two-date contract, tested at the boundary where it would quietly break."""

import json

from vintage import envelope


def make_row(**over):
    base = dict(
        entity="AAPL",
        field="us-gaap:Assets",
        observed_at="2019-09-28",
        value=338516000000,
        source="sec-edgar-xbrl",
        source_url="https://example.invalid",
        known_at="2019-10-31",
    )
    base.update(over)
    return envelope.row(**base)


def test_known_at_implies_as_filed_vintage():
    assert make_row()["vintage"] == envelope.AS_FILED


def test_missing_known_at_is_flagged_never_guessed():
    r = make_row(known_at=None)
    assert r["vintage"] == envelope.UNKNOWN_VINTAGE
    assert r["known_at"] is None


def test_visible_at_drops_rows_published_after_the_cutoff():
    rows = [
        make_row(known_at="2019-10-31", value=1),
        make_row(known_at="2020-10-30", value=2),
    ]
    visible = envelope.visible_at(rows, "2020-01-01")
    assert [r["value"] for r in visible] == [1]


def test_visible_at_is_strict_not_inclusive_of_the_future():
    rows = [make_row(known_at="2020-01-02")]
    assert envelope.visible_at(rows, "2020-01-01") == []
    assert len(envelope.visible_at(rows, "2020-01-02")) == 1


def test_visible_at_without_a_cutoff_keeps_everything():
    rows = [make_row(), make_row(known_at=None)]
    assert len(envelope.visible_at(rows, None)) == 2


def test_unknown_vintage_rows_survive_filtering_but_raise_a_warning():
    rows = [make_row(known_at=None, source="yahoo-finance")]
    assert len(envelope.visible_at(rows, "2015-01-01")) == 1
    warnings = envelope.warn_unknown_vintage(rows)
    assert warnings and "yahoo-finance" in warnings[0]


def test_no_warning_when_every_row_carries_a_filing_date():
    assert envelope.warn_unknown_vintage([make_row()]) == []


def test_restatements_report_versions_oldest_first():
    rows = [
        make_row(value=200, known_at="2021-10-29"),
        make_row(value=100, known_at="2019-10-31"),
    ]
    found = envelope.restatements(rows)
    assert len(found) == 1
    assert [v["value"] for v in found[0]["versions"]] == [100, 200]


def test_a_period_reported_twice_with_one_value_is_not_a_restatement():
    rows = [make_row(known_at="2019-10-31"), make_row(known_at="2020-10-30")]
    assert envelope.restatements(rows) == []


def test_respond_counts_rows_and_collects_sources():
    body = json.loads(envelope.respond("fetch", rows=[make_row()]))
    assert body["ok"] is True
    assert body["verb"] == "fetch"
    assert body["row_count"] == 1
    assert body["sources"] == ["sec-edgar-xbrl"]


def test_fail_carries_a_hint_instead_of_a_bare_not_found():
    body = json.loads(envelope.fail("resolve", "no match", did_you_mean=["AAPL"]))
    assert body["ok"] is False
    assert body["did_you_mean"] == ["AAPL"]
