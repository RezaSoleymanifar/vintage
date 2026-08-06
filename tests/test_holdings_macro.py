"""13F holdings, BLS and BEA.

Each of the three carries one convention that turns into a wrong number rather
than an error: the 2023 change from thousands to dollars, BLS filing annual
averages as a thirteenth month, and BEA holding a power of ten back in
UNIT_MULT. Those are what these tests guard.
"""

import pytest

from vintage import envelope, registry
from vintage.sources import bea, bls, thirteenf


@pytest.mark.parametrize("field,expected", [
    ("13f:value", "thirteenf"),
    ("13f:shares", "thirteenf"),
    ("bls:CUUR0000SA0", "bls"),
    ("bea:T10101", "bea"),
])
def test_prefixes_route(field, expected):
    assert registry.route(field) == expected


def test_the_new_sources_are_declared():
    named = {s["source"] for s in registry.SOURCES}
    assert {"sec-form-13f", "bls", "bea"} <= named


# ------------------------------------------------------------------ 13F units


INFO_TABLE = b"""<?xml version="1.0"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>ALLY FINL INC</nameOfIssuer><titleOfClass>COM</titleOfClass>
    <cusip>02005N100</cusip><value>498992850</value>
    <shrsOrPrnAmt><sshPrnamt>12719675</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
    <investmentDiscretion>DFND</investmentDiscretion>
    <votingAuthority><Sole>12719675</Sole><Shared>0</Shared><None>0</None></votingAuthority>
  </infoTable>
  <infoTable>
    <nameOfIssuer>ALLY FINL INC</nameOfIssuer><titleOfClass>COM</titleOfClass>
    <cusip>02005N100</cusip><value>109996016</value>
    <shrsOrPrnAmt><sshPrnamt>2803875</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
    <investmentDiscretion>DFND</investmentDiscretion>
    <votingAuthority><Sole>2803875</Sole><Shared>0</Shared><None>0</None></votingAuthority>
  </infoTable>
  <infoTable>
    <nameOfIssuer>NVIDIA CORPORATION</nameOfIssuer><titleOfClass>COM</titleOfClass>
    <cusip>67066G104</cusip><value>1000000</value>
    <shrsOrPrnAmt><sshPrnamt>1000</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
    <putCall>Put</putCall>
    <votingAuthority><Sole>0</Sole><Shared>0</Shared><None>1000</None></votingAuthority>
  </infoTable>
</informationTable>"""


def scaled(raw: bytes, filed: str = "2026-05-15") -> list[dict]:
    """Lines as `assemble` prepares them, so `merge` sees dollars."""
    scale = 1.0 if filed >= thirteenf.DOLLARS_FROM else 1_000.0
    out = []
    for line in thirteenf.parse(raw):
        line["value_usd"] = line.pop("value_raw") * scale
        line["filed"], line["form"], line["accession"] = filed, "13F-HR", "x"
        out.append(line)
    return out


def test_lines_split_across_sub_advisers_are_summed():
    """Berkshire files Ally three times. Taking the first row understates the
    position; counting rows overstates the number of holdings."""
    merged = thirteenf.merge(scaled(INFO_TABLE))
    ally = next(h for h in merged if h["cusip"] == "02005N100")
    assert ally["line_items"] == 2
    assert ally["shares"] == 12_719_675 + 2_803_875
    assert ally["value_usd"] == 498_992_850 + 109_996_016
    assert len(merged) == 2


def test_a_pre_2023_line_is_scaled_from_thousands():
    merged = thirteenf.merge(scaled(INFO_TABLE, filed="2019-11-14"))
    ally = next(h for h in merged if h["cusip"] == "02005N100")
    assert ally["value_usd"] == (498_992_850 + 109_996_016) * 1_000


def test_an_amended_line_carries_the_later_date():
    """Merging an amendment into an original must not backdate the amendment."""
    merged = thirteenf.merge(
        scaled(INFO_TABLE, filed="2026-05-15") + scaled(INFO_TABLE, filed="2026-08-01")
    )
    assert all(h["filed"] == "2026-08-01" for h in merged)


def test_puts_are_kept_apart_from_the_common():
    merged = thirteenf.merge(scaled(INFO_TABLE))
    assert {h["put_call"] for h in merged} == {None, "Put"}


def test_an_empty_table_is_an_error_not_an_empty_answer():
    with pytest.raises(thirteenf.SourceError):
        thirteenf.parse(b"<informationTable></informationTable>")


def test_the_dollars_boundary_is_the_documented_one():
    """Filings from 3 January 2023 report dollars; everything before reports
    thousands, and nothing in the document says which."""
    assert thirteenf.DOLLARS_FROM == "2023-01-03"
    assert "2019-11-14" < thirteenf.DOLLARS_FROM <= "2023-01-03"


# --------------------------------------------------------------- 13F vintage


FILINGS = [
    {"form": "13F-HR", "accession": "d", "filed": "2026-05-15", "period": "2026-03-31"},
    {"form": "13F-HR", "accession": "c", "filed": "2026-02-17", "period": "2025-12-31"},
    {"form": "13F-HR/A", "accession": "b", "filed": "2025-08-14", "period": "2025-03-31"},
    {"form": "13F-HR", "accession": "a", "filed": "2025-05-15", "period": "2025-03-31"},
]


def test_the_latest_quarter_wins_when_no_date_is_given():
    picked = thirteenf.chain(FILINGS, quarter=None, as_of=None)
    assert [f["accession"] for f in picked] == ["d"]


def test_as_of_returns_the_book_that_was_actually_on_file():
    """Six weeks after a quarter ends, the public record is still the previous
    quarter. That gap is the whole reason this source exists."""
    picked = thirteenf.chain(FILINGS, quarter=None, as_of="2026-04-30")
    assert [f["period"] for f in picked] == ["2025-12-31"]
    assert picked[0]["filed"] == "2026-02-17"


def test_a_quarter_returns_its_whole_amendment_chain_oldest_first():
    """An amendment can add to the original instead of replacing it, so the
    quarter is the chain and not the last document in it."""
    picked = thirteenf.chain(FILINGS, quarter="2025-03-31", as_of=None)
    assert [f["accession"] for f in picked] == ["a", "b"]


def test_an_amendment_is_absent_until_it_is_filed():
    early = thirteenf.chain(FILINGS, quarter="2025-03-31", as_of="2025-06-01")
    assert [f["accession"] for f in early] == ["a"]


def test_a_quarter_can_be_named_by_year():
    picked = thirteenf.chain(FILINGS, quarter="2025", as_of=None)
    assert {f["period"] for f in picked} == {"2025-12-31"}


def test_asking_before_the_first_filing_says_what_exists():
    with pytest.raises(thirteenf.SourceError) as exc:
        thirteenf.chain(FILINGS, quarter=None, as_of="2001-01-01")
    assert "2025-03-31" in str(exc.value)


def test_the_shortcuts_are_ten_digit_ciks():
    assert all(len(cik) == 10 and cik.isdigit()
               for cik, _ in thirteenf.MANAGERS.values())
    assert thirteenf.MANAGERS["BERKSHIRE"][0] == "0001067983"


def test_holdings_are_one_side_of_a_book():
    rows = [{"filer": "X", "observed_at": "2025-12-31", "known_at": "2026-02-14",
             "form": "13F-HR", "reported_unit": "USD", "line_items": 1}]
    notes = thirteenf.warnings_for(rows)
    assert "45 days later" in notes[0]
    assert "Short positions" in notes[1]


def test_a_pre_2023_filing_says_it_was_rescaled():
    rows = [{"filer": "X", "observed_at": "2019-12-31", "known_at": "2020-02-14",
             "form": "13F-HR", "reported_unit": "USD thousands", "line_items": 1}]
    assert any("thousands" in n for n in thirteenf.warnings_for(rows))


def test_a_new_holdings_amendment_is_called_out_as_additive():
    """Read as a replacement it turns an eleven-position book into one."""
    rows = [{"filer": "X", "observed_at": "2024-12-31", "known_at": "2025-02-14",
             "form": "13F-HR", "reported_unit": "USD", "line_items": 1,
             "filing_chain": "13F-HR 2025-02-14; 13F-HR/A 2025-04-16 NEW HOLDINGS"}]
    note = next(n for n in thirteenf.warnings_for(rows) if "/A" in n)
    assert "adds positions to the original" in note


def test_a_restated_amendment_is_called_out_as_a_replacement():
    rows = [{"filer": "X", "observed_at": "2024-12-31", "known_at": "2025-02-14",
             "form": "13F-HR", "reported_unit": "USD", "line_items": 1,
             "filing_chain": "13F-HR 2025-02-14; 13F-HR/A 2025-04-16 RESTATED"}]
    note = next(n for n in thirteenf.warnings_for(rows) if "/A" in n)
    assert "replaces the original table" in note


# ------------------------------------------------------------------------ BLS


@pytest.mark.parametrize("year,period,expected,freq", [
    ("2024", "M01", "2024-01-31", "monthly"),
    ("2024", "M02", "2024-02-29", "monthly"),   # a leap February
    ("2023", "M02", "2023-02-28", "monthly"),
    ("2024", "M12", "2024-12-31", "monthly"),
    ("2024", "M13", "2024-12-31", "annual"),    # the annual average
    ("2024", "Q02", "2024-06-30", "quarterly"),
    ("2024", "Q05", "2024-12-31", "annual"),
    ("2024", "A01", "2024-12-31", "annual"),
    ("2024", "M14", None, "unknown"),
])
def test_bls_periods_map_to_dates(year, period, expected, freq):
    assert bls.period_end(year, period) == (expected, freq)


def test_the_thirteenth_month_is_flagged_not_dropped():
    """M13 is the annual average filed as a month. Summed with the monthly
    prints it counts the year twice."""
    rows = [{"frequency": "annual"}, {"frequency": "monthly"}]
    notes = bls.warnings_for("bls:CUUR0000SA0", rows)
    assert any("annual averages" in n for n in notes)


def test_bls_admits_it_has_no_release_date():
    notes = bls.warnings_for("bls:CUUR0000SA0", [])
    assert "no known_at" in notes[0]
    assert "fred:" in notes[0]


@pytest.mark.parametrize("start,end,span,expected", [
    ("2015", "2020", 10, [(2015, 2020)]),
    ("2000", "2026", 10, [(2017, 2026), (2007, 2016), (2000, 2006)]),
    (None, None, 10, []),
])
def test_windows_split_into_spans_the_api_accepts(start, end, span, expected):
    assert bls.windows(start, end, span) == expected


def test_a_backwards_window_is_refused():
    with pytest.raises(bls.SourceError):
        bls.windows("2020", "2010", 10)


def test_the_curated_shortlist_covers_the_headline_prints():
    fields = {c["field"] for c in bls.catalog()}
    assert {"bls:CUUR0000SA0", "bls:LNS14000000", "bls:CES0000000001"} <= fields
    assert all(c["vintage"] == envelope.UNKNOWN_VINTAGE for c in bls.catalog())


# ------------------------------------------------------------------------ BEA


@pytest.mark.parametrize("spec,expected", [
    ("T10101", ("NIPA", "T10101", None)),
    ("t10101", ("NIPA", "T10101", None)),
    ("NIPA/T20600", ("NIPA", "T20600", None)),
    ("NIPA/T20600/M", ("NIPA", "T20600", "M")),
])
def test_bea_specs_parse(spec, expected):
    assert bea.parse_spec(spec) == expected


@pytest.mark.parametrize("raw,expected", [
    ("2024Q1", ("2024-03-31", "quarterly")),
    ("2024Q4", ("2024-12-31", "quarterly")),
    ("2024M02", ("2024-02-29", "monthly")),
    ("2024", ("2024-12-31", "annual")),
    ("2024M13", (None, "unknown")),
    ("", (None, "unknown")),
])
def test_bea_periods_parse(raw, expected):
    assert bea.period_end(raw) == expected


def test_bea_says_the_number_is_not_the_first_print():
    """GDP is published three times before the first annual revision. This is
    the single most common way a macro backtest looks ahead."""
    notes = bea.warnings_for("T10101", [{"entity": "T10101:L1", "observed_at": "2024-03-31"}])
    assert "advance estimate" in notes[0]
    assert "fred:GDPC1" in notes[0]


@pytest.mark.asyncio
async def test_bea_without_a_key_says_where_to_get_one():
    with pytest.raises(bea.SourceError) as exc:
        await bea.table("T10101")
    assert "apps.bea.gov/API/signup" in str(exc.value)


@pytest.mark.asyncio
async def test_an_impossible_frequency_is_refused_before_the_call():
    with pytest.raises(bea.SourceError) as exc:
        await bea.table("T10101", frequency="D")
    assert "A, Q or M" in str(exc.value)


# --------------------------------------------------------------------- network


@pytest.mark.network
@pytest.mark.asyncio
async def test_berkshires_coca_cola_stake_is_the_famous_round_number():
    rows = await thirteenf.holdings("BERKSHIRE")
    coke = next(r for r in rows if r["cusip"] == "191216100")
    assert coke["shares"] == 400_000_000
    assert coke["known_at"] > coke["observed_at"]


@pytest.mark.network
@pytest.mark.asyncio
async def test_a_pre_2023_filing_is_rescaled_to_dollars():
    """Apple, 2019Q4: 245,155,566 shares at a 293.65 close is $71.99bn. The
    filing says 71,989,933 because it is quoting thousands."""
    rows = await thirteenf.holdings("BERKSHIRE", as_of="2020-03-01")
    assert rows[0]["observed_at"] == "2019-12-31"
    assert rows[0]["known_at"] == "2020-02-14"
    apple = next(r for r in rows if r["cusip"] == "037833100")
    assert apple["shares"] == 245_155_566
    assert 71e9 < apple["market_value_usd"] < 73e9
    assert apple["reported_unit"] == "USD thousands"


@pytest.mark.network
@pytest.mark.asyncio
async def test_an_additive_amendment_does_not_shrink_the_portfolio():
    """Pershing Square's December 2024 amendment lists one position. Taking it
    as the quarter's table replaces an eleven-name book with Hertz alone."""
    rows = await thirteenf.holdings("PERSHING", quarter="2024-12-31")
    assert len(rows) > 5
    hertz = next(r for r in rows if "HERTZ" in (r["issuer"] or ""))
    assert hertz["known_at"] == "2025-04-16"
    assert any(r["known_at"] == "2025-02-14" for r in rows)


@pytest.mark.network
@pytest.mark.asyncio
async def test_a_position_added_by_amendment_is_hidden_until_it_is_filed():
    rows = await thirteenf.holdings("PERSHING", quarter="2024-12-31", as_of="2025-03-01")
    assert not any("HERTZ" in (r["issuer"] or "") for r in rows)


@pytest.mark.network
@pytest.mark.asyncio
async def test_a_manager_resolves_by_name_as_well_as_shortcut():
    assert (await thirteenf.find("scion asset"))["cik"] == "0001649339"
    assert (await thirteenf.find("0001067983"))["cik"] == "0001067983"


@pytest.mark.network
@pytest.mark.asyncio
async def test_bls_honours_the_window_it_was_given():
    """The keyless GET route ignores startyear and returns the last three
    years instead, which is a wrong answer rather than an error."""
    rows = await bls.series("CES0000000001", start="2015-01-01", end="2020-12-31")
    assert rows[0]["observed_at"] == "2015-01-31"
    assert rows[-1]["observed_at"] == "2020-12-31"
    assert all(r["known_at"] is None for r in rows)
    assert all(r["vintage"] == envelope.UNKNOWN_VINTAGE for r in rows)
