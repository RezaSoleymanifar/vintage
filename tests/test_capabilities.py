"""The capability map is the agent's map of the surface, so it must not drift.

Every check here exists because a specific kind of lie is possible: a prefix
the router knows but the map does not describe, a map entry pointing at a
source that no longer exists, an example that would not run, or a prefix that
routes to an adapter `fetch` never branches on — which is how `filing:` sat in
the router for months while every fetch of it returned "no source answers".
"""

import json

import pytest

from vintage import registry, server


def test_every_routed_prefix_is_described():
    missing = set(registry.PREFIXES) - set(registry.PREFIX_SPECS)
    assert not missing, f"prefixes with no capability entry: {sorted(missing)}"


def test_no_capability_describes_a_prefix_that_does_not_route():
    extra = set(registry.PREFIX_SPECS) - set(registry.PREFIXES)
    assert not extra, f"capability entries for unrouted prefixes: {sorted(extra)}"


def test_every_adapter_maps_to_a_real_source():
    names = {s["source"] for s in registry.SOURCES}
    for adapter in set(registry.PREFIXES.values()):
        source = registry.ADAPTER_SOURCE.get(adapter)
        assert source, f"adapter {adapter!r} has no ADAPTER_SOURCE entry"
        assert source in names, f"{adapter!r} points at unknown source {source!r}"


@pytest.mark.parametrize("cap", registry.capabilities(), ids=lambda c: c["prefix"])
def test_capability_rows_are_usable(cap):
    """Each row has to be enough to make a call without reading anything else."""
    assert cap["example"]["args"]["field"].startswith(cap["prefix"])
    assert cap["verb"] in {"fetch", "events"}
    assert cap["as_of"] in {"enforced", "partial", "none"}
    assert cap["answers"]
    if cap["needs_entity"]:
        assert cap["entity_example"], "an entity is required but no example is given"
        assert cap["example"]["args"]["entity"] == cap["entity_example"]
    else:
        assert "entity" not in cap["example"]["args"]


def test_fetchable_prefixes_are_ones_fetch_actually_branches_on():
    for prefix, adapter in registry.PREFIXES.items():
        if registry.PREFIX_SPECS[prefix]["verb"] == "fetch":
            assert adapter in registry.FETCH_ADAPTERS, (
                f"{prefix!r} claims to be fetchable but routes to {adapter!r}, "
                "which fetch does not handle"
            )


def test_capability_for_finds_the_owning_prefix():
    assert registry.capability_for("us-gaap:Assets")["prefix"] == "us-gaap:"
    assert registry.capability_for("13f:value")["prefix"] == "13f:"
    assert registry.capability_for("nonsense:thing") is None


def test_nearest_prefixes_never_returns_nothing():
    for field in ["shortvol:x", "zzz:qq", "vix", "holdings:value"]:
        near = registry.nearest_prefixes(field)
        assert near, f"no suggestion for {field!r}"
        assert all("example" in n for n in near)


def test_payload_is_self_describing():
    payload = server._capability_payload()
    assert payload["fields"], "no fields advertised"
    assert payload["verbs"][0]["verb"] == "capabilities"
    assert payload["house_rules"]
    # The derived index lists must agree with the rows they summarise.
    assert payload["entity_required"] == sorted(
        c["prefix"] for c in payload["fields"] if c["needs_entity"]
    )
    assert payload["needs_api_key"] == sorted(
        c["prefix"] for c in payload["fields"] if c["key_required"]
    )


@pytest.mark.parametrize(
    "query,expected_prefix",
    [
        ("holdings", "13f:"),
        ("short volume", "short:"),
        ("published anomalies", "openap:"),
        ("delisting", "delisting:"),
        ("forum mention", "ape:"),
        ("fundamentals", "us-gaap:"),
    ],
)
def test_discover_can_reach_a_prefix_by_what_it_answers(query, expected_prefix):
    """The prefixes used to be invisible to search — you had to know the name."""
    hits = registry.search_static(query, limit=8)
    assert any(h["field"].startswith(expected_prefix) for h in hits), (
        f"{query!r} found {[h['field'] for h in hits]}"
    )


def test_prefix_rows_never_shadow_a_named_catalog_entry():
    named = {i["field"] for i in registry.static_catalog() if i.get("kind") != "prefix"}
    prefixes = [i for i in registry.static_catalog() if i.get("kind") == "prefix"]
    assert not (named & {p["field"] for p in prefixes})


def test_payload_serializes():
    """It travels as JSON over the wire, so it has to survive the trip."""
    blob = json.loads(server.capabilities_resource())
    assert {c["prefix"] for c in blob["fields"]} == set(registry.PREFIXES)
