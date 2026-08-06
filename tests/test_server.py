"""The published surface: six verbs plus status, and errors that teach."""

import json

import pytest

from vintage import __version__
from vintage.server import mcp, resolve, status

VERBS = {"resolve", "discover", "fetch", "events", "backtest", "benchmark"}

# Two tools that are not verbs: `status` reports the server's own state and
# `capabilities` describes the surface. Neither is a data source, and the list
# is closed — a new source must still add zero tools.
META = {"status", "capabilities"}


@pytest.mark.asyncio
async def test_exactly_the_six_verbs_plus_meta_are_exposed():
    """Adding a source must not add a tool. If this fails, that promise broke."""
    names = {tool.name for tool in await mcp.list_tools()}
    assert names == VERBS | META


@pytest.mark.asyncio
async def test_every_tool_carries_a_description_for_the_model():
    for tool in await mcp.list_tools():
        assert tool.description and len(tool.description) > 40


def test_server_version_tracks_the_package_version():
    assert mcp.version == __version__


def test_instructions_state_the_two_date_contract():
    assert "known_at" in mcp.instructions
    assert "observed_at" in mcp.instructions


@pytest.mark.asyncio
async def test_status_reports_without_touching_the_network():
    body = json.loads(await status())
    assert body["ok"] is True
    assert body["specs_tried_this_session"] == 0
    assert isinstance(body["fred_key_configured"], bool)
    assert {s["source"] for s in body["sources"]} >= {"fred", "sec-edgar-xbrl"}


@pytest.mark.asyncio
async def test_resolve_rejects_an_empty_identifier_offline():
    body = json.loads(await resolve("   "))
    assert body["ok"] is False
    assert body["verb"] == "resolve"
