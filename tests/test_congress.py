"""The House PTR parser, tested on the shape the Clerk's PDFs actually produce.

The sample below is extracted text from filing 20026537, trimmed. Keeping a
real fixture rather than an invented one is the point: the layout is a table
flattened into a stream, and inventing a tidier version would test a parser
that does not have to exist.
"""

import pytest

from vintage.registry import FETCH_ADAPTERS, PREFIXES, route
from vintage.sources import congress

REAL = """SP Rollins, Inc. Common Stock (ROL)
[ST]
P 12/12/202401/08/2025$15,001 -
$50,000
F      S     : New
SP US TREASU NOTE 4.375% DUE
12/15/26 (91282CJP7) [GS]
P 12/03/202401/08/2025$100,001 -
$250,000
F      S     : New
Apple Inc. (AAPL) [ST]
S 03/04/202503/20/2025$1,001 -
$15,000
Microsoft Corp (MSFT) [ST]
S (partial) 03/05/202503/20/2025$50,001 -
$100,000
"""


@pytest.fixture
def parsed():
    return congress.parse_ptr(REAL)


def test_pulls_the_equity_trades(parsed):
    tickers = [t["ticker"] for t in parsed]
    assert "ROL" in tickers
    assert "AAPL" in tickers
    assert "MSFT" in tickers


def test_a_cusip_is_not_mistaken_for_a_ticker(parsed):
    """Treasuries sit in the same parenthesised slot as a ticker.

    91282CJP7 is a CUSIP. Nine characters is the tell, and letting it through
    would invent a security that does not trade under that symbol.
    """
    assert "91282CJP7" not in [t["ticker"] for t in parsed]


def test_purchases_and_sales_are_told_apart(parsed):
    actions = {t["ticker"]: t["action"] for t in parsed}
    assert actions["ROL"] == "purchase"
    assert actions["AAPL"] == "sale"
    assert actions["MSFT"] == "partial sale"


def test_trade_date_and_disclosure_date_are_kept_separate(parsed):
    rollins = next(t for t in parsed if t["ticker"] == "ROL")
    assert rollins["observed_at"] == "2024-12-12"
    assert rollins["known_at"] == "2025-01-08"
    assert rollins["observed_at"] < rollins["known_at"]


def test_amount_is_a_band_not_a_figure(parsed):
    rollins = next(t for t in parsed if t["ticker"] == "ROL")
    assert rollins["amount_low"] == 15001
    assert rollins["amount_high"] == 50000


def test_rows_without_a_full_transaction_are_skipped():
    """An asset line with no dates and no band is not half a trade."""
    assert congress.parse_ptr("Some Company Inc. (XYZ) [ST]\nheld, no transaction\n") == []


def test_disclosure_lag_is_measured_from_the_trade():
    assert congress._lag("2025-01-01", "2025-02-15") == 45
    assert congress._lag("nonsense", "2025-02-15") is None


def test_warnings_never_let_the_midpoint_pass_as_a_flow():
    notes = " ".join(congress.warnings_for([]))
    assert "midpoint" in notes
    assert "Never sum it" in notes


def test_warnings_flag_filings_past_the_statutory_deadline():
    rows = [{"disclosure_lag_days": 120}, {"disclosure_lag_days": 10}]
    notes = " ".join(congress.warnings_for(rows))
    assert "past the STOCK Act deadline" in notes


# Trimmed from the real EFD page for PTR 57cf1745, which is a proper HTML
# table rather than the House's flattened PDF.
SENATE = """<table>
<tr><th>&#35;</th><th>Transaction Date</th><th>Owner</th><th>Ticker</th>
<th>Asset Name</th><th>Asset Type</th><th>Type</th><th>Amount</th><th>Comment</th></tr>
<tr><td>5</td><td>12/17/2025</td><td>Self</td><td>XLU</td>
<td>SPDR Select Sector Fund - Utilities</td><td>Stock</td><td>Purchase</td>
<td>$15,001 - $50,000</td><td>--</td></tr>
<tr><td>4</td><td>12/17/2025</td><td>Spouse</td><td>AAPL</td>
<td>Apple Inc</td><td>Stock</td><td>Sale (Partial)</td>
<td>$50,001 - $100,000</td><td>--</td></tr>
<tr><td>3</td><td>10/07/2025</td><td>Self</td><td>--</td>
<td>Some Municipal Bond</td><td>Other</td><td>Sale (Full)</td>
<td>$1,001 - $15,000</td><td>--</td></tr>
</table>"""


@pytest.fixture
def senate():
    return congress.parse_senate_ptr(SENATE)


def test_senate_reads_the_table_columns(senate):
    assert [t["ticker"] for t in senate] == ["XLU", "AAPL"]


def test_senate_maps_its_own_transaction_wording(senate):
    actions = {t["ticker"]: t["action"] for t in senate}
    assert actions["XLU"] == "purchase"
    assert actions["AAPL"] == "partial sale"


def test_senate_drops_holdings_with_no_ticker(senate):
    """EFD prints "--" where there is no symbol, and a trade with no symbol
    cannot be joined to a price series."""
    assert all(t["ticker"] != "--" for t in senate)
    assert len(senate) == 2


def test_senate_keeps_the_owner(senate):
    owners = {t["ticker"]: t["owner"] for t in senate}
    assert owners["AAPL"] == "Spouse"


def test_senate_header_row_is_not_a_trade(senate):
    assert all(t["observed_at"].startswith("20") for t in senate)


def test_warnings_name_the_missing_chamber():
    house_only = [{"chamber": "House", "disclosure_lag_days": 12}]
    notes = " ".join(congress.warnings_for(house_only))
    assert "Senate" in notes and "not all of" in notes


def test_warnings_stay_quiet_when_both_chambers_are_present():
    both = [{"chamber": "House"}, {"chamber": "Senate"}]
    notes = " ".join(congress.warnings_for(both))
    assert "not all of" not in notes


def test_warnings_always_carry_the_statutory_restriction():
    notes = " ".join(congress.warnings_for([{"chamber": "House"}, {"chamber": "Senate"}]))
    assert "Ethics in Government Act" in notes


def test_the_prefix_is_wired_into_the_router():
    assert PREFIXES["congress:"] == "congress"
    for field in ("congress:trades", "congress:house", "congress:senate"):
        assert route(field) == "congress"
    assert "congress" in FETCH_ADAPTERS


def test_the_catalog_advertises_both_chambers():
    fields = [c["field"] for c in congress.catalog()]
    assert "congress:trades" in fields
    assert "congress:house" in fields
    assert "congress:senate" in fields
