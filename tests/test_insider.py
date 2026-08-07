"""The Form 4 parser, on the shape EDGAR actually serves.

The fixture is trimmed from Apple's filing 0001140361-26-025622, which is a
good test precisely because nothing in it was a decision: an option exercised
and shares withheld to pay the tax on it. A parser that reports those as
insider buying and selling is worse than no parser.
"""

import pytest

from vintage.registry import FETCH_ADAPTERS, PREFIXES, route
from vintage.sources import insider

FORM4 = """<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType>
  <periodOfReport>2026-06-15</periodOfReport>
  <issuer>
    <issuerCik>0000320193</issuerCik>
    <issuerName>Apple Inc.</issuerName>
    <issuerTradingSymbol>AAPL</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>Newstead Jennifer</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>0</isDirector>
      <isOfficer>true</isOfficer>
      <officerTitle>SVP, GC and Secretary</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-06-15</value></transactionDate>
      <transactionCoding><transactionCode>M</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>30104</value></transactionShares>
        <transactionPricePerShare><footnoteId id="F1"/></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction><value>57784</value></sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-06-15</value></transactionDate>
      <transactionCoding><transactionCode>F</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>16238</value></transactionShares>
        <transactionPricePerShare><value>296.42</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-06-16</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>1000</value></transactionShares>
        <transactionPricePerShare><value>295.14</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""


@pytest.fixture
def filing():
    return insider.parse(FORM4.encode())


def test_reads_the_insider_and_their_role(filing):
    assert filing["owner"] == "Newstead Jennifer"
    assert filing["title"] == "SVP, GC and Secretary"
    assert filing["roles"] == ["officer"]


def test_a_false_flag_is_not_a_role(filing):
    """isDirector is 0 here. Treating any present tag as true would promote
    every officer to the board."""
    assert "director" not in filing["roles"]


def test_the_transaction_code_survives(filing):
    assert [t["code"] for t in filing["transactions"]] == ["M", "F", "P"]


def test_compensation_mechanics_are_not_called_trades(filing):
    """The whole point. M is an option exercising and F is tax withholding;
    neither is anybody deciding to buy or sell that morning."""
    by_code = {t["code"]: t for t in filing["transactions"]}
    assert by_code["M"]["open_market"] is False
    assert by_code["F"]["open_market"] is False
    assert by_code["P"]["open_market"] is True


def test_acquired_and_disposed_are_told_apart(filing):
    by_code = {t["code"]: t for t in filing["transactions"]}
    assert by_code["F"]["direction"] == "disposed"
    assert by_code["P"]["direction"] == "acquired"


def test_a_footnoted_price_is_none_not_zero(filing):
    """The exercise price sits in a footnote. Zero would silently sum into a
    dollar total and understate it."""
    exercise = next(t for t in filing["transactions"] if t["code"] == "M")
    assert exercise["price"] is None
    assert exercise["usd"] is None
    assert exercise["shares"] == 30104


def test_dollar_value_is_shares_times_price(filing):
    purchase = next(t for t in filing["transactions"] if t["code"] == "P")
    assert purchase["usd"] == pytest.approx(1000 * 295.14)


def test_unknown_codes_do_not_become_open_market():
    """A code outside the table must default to 'not a decision', because the
    failure that matters is inventing insider buying that never happened."""
    odd = FORM4.replace("<transactionCode>P</transactionCode>",
                        "<transactionCode>Z</transactionCode>")
    parsed = insider.parse(odd.encode())
    unknown = next(t for t in parsed["transactions"] if t["code"] == "Z")
    assert unknown["open_market"] is False


def test_malformed_xml_is_an_error_not_an_empty_result():
    from vintage.http import SourceError

    with pytest.raises(SourceError):
        insider.parse(b"<ownershipDocument><unclosed>")


def test_warnings_count_the_mechanics():
    rows = [{"open_market": False, "usd": None, "filing_lag_days": 2},
            {"open_market": True, "usd": 100.0, "filing_lag_days": 1}]
    notes = " ".join(insider.warnings_for(rows))
    assert "1 of 2 transactions here were compensation mechanics" in notes
    assert "insider:open_market" in notes


def test_the_prefix_is_wired_into_the_router():
    assert PREFIXES["insider:"] == "insider"
    assert route("insider:open_market") == "insider"
    assert "insider" in FETCH_ADAPTERS


def test_the_catalog_advertises_both_fields():
    fields = [c["field"] for c in insider.catalog()]
    assert "insider:trades" in fields
    assert "insider:open_market" in fields
