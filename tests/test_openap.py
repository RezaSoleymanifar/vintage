"""OpenAP is the scoreboard published claims get judged against, so the
claim-shaped fields matter more than the row count."""

import pytest

from vintage import envelope, registry
from vintage.sources import openap

def test_prefix_routes_to_openap():
    assert registry.route("openap:Mom12m") == "openap"


def test_source_is_declared_as_keyless():
    entry = next(s for s in registry.SOURCES if s["source"] == openap.SOURCE)
    assert entry["key_required"] is False


def test_every_data_category_has_an_honest_support_verdict():
    """A category with no verdict would silently claim to be replicable."""
    for category, verdict in openap.DATA_CATEGORY_SUPPORT.items():
        assert verdict, category
    assert "supported" in openap.DATA_CATEGORY_SUPPORT["Price"]
    assert "unsupported" in openap.DATA_CATEGORY_SUPPORT["Options"]


@pytest.mark.network
async def test_load_returns_the_documented_predictors():
    rows = await openap.load()
    assert len(rows) > 300
    assert all(r["source"] == openap.SOURCE for r in rows)


@pytest.mark.network
async def test_claims_are_immutable_and_dated_to_publication():
    """A 1993 claim does not change when a 2020 replication disagrees."""
    row = await openap.get("Mom12m")
    assert row["vintage"] == envelope.IMMUTABLE
    assert row["known_at"].startswith("1993")


@pytest.mark.network
async def test_jegadeesh_titman_carries_the_number_to_beat():
    row = await openap.get("Mom12m")
    assert "Jegadeesh" in row["authors"]
    assert row["value"] == pytest.approx(1.31, abs=0.01)
    assert row["t_stat"] == pytest.approx(3.74, abs=0.01)
    assert row["sample_start"] == "1964"
    assert row["data_category"] == "Price"


@pytest.mark.network
async def test_lookup_is_case_insensitive():
    assert (await openap.get("mom12m"))["entity"] == "Mom12m"


@pytest.mark.network
async def test_unknown_acronym_teaches_instead_of_saying_not_found():
    with pytest.raises(openap.SourceError) as exc:
        await openap.get("Mom99z")
    message = str(exc.value)
    assert "discover" in message
    assert "Mom12m" in message  # suggested from the shared prefix


@pytest.mark.network
async def test_search_ranks_the_famous_paper_first():
    hits = await openap.search("momentum", limit=5)
    assert hits
    assert hits[0]["field"].startswith("openap:Mom")


@pytest.mark.network
async def test_price_only_subset_is_what_vintage_can_replicate_today():
    price = openap.supported_only(await openap.load())
    assert 40 < len(price) < 80
    assert all(r["data_category"] == "Price" for r in price)
    assert all("supported" in r["vintage_support"] for r in price)
