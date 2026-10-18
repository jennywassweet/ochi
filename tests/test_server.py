"""The MCP surface: tools are registered and wired, talking to a client over in-memory streams."""
from __future__ import annotations

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from ochi import browser, chrome, discogs_api, server

pytestmark = pytest.mark.anyio

TOOLS = {"fetch", "look", "show", "tabs", "browser_start", "browser_status", "list_extractors", "snapshot",
         "discogs_search", "discogs_release", "discogs_master_versions", "discogs_listing"}


async def call(name, **args):
    async with create_connected_server_and_client_session(server.mcp) as client:
        res = await client.call_tool(name, args)
    return res.isError, "".join(c.text for c in res.content if c.type == "text")


async def test_tools_are_listed_with_descriptions():
    async with create_connected_server_and_client_session(server.mcp) as client:
        tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == TOOLS
    for t in tools:
        assert t.description, t.name


async def test_list_extractors():
    err, text = await call("list_extractors")
    assert not err
    assert "- discogs-market:" in text and "- generic: *" in text


async def test_fetch_uses_matching_extractor(monkeypatch):
    seen = {}

    async def run(url, ex):
        seen["ex"] = ex.name
        return {"total": 1, "items": [{"id": 1}]}

    monkeypatch.setattr(browser, "run", run)
    err, text = await call("fetch", url="https://www.reddit.com/r/x/comments/1/t/", max_chars=1000)
    assert not err
    assert seen["ex"] == "reddit-thread"
    assert text == '[extractor: reddit-thread]\n{"total": 1}\n{"id": 1}'


async def test_browser_status_does_not_start_anything(monkeypatch):
    monkeypatch.setattr(chrome, "version", lambda: None)
    assert await call("browser_status") == (False, "not running")
    monkeypatch.setattr(chrome, "version", lambda: {"Browser": "Chrome/1.2"})
    assert await call("browser_status") == (False, "running: Chrome/1.2")


async def test_discogs_tool_renders_list_as_json_lines(monkeypatch):
    monkeypatch.setattr(discogs_api, "search", lambda *a: [{"id": 1, "title": "Ä"}, {"id": 2}])
    assert await call("discogs_search", q="x") == (False, '{"id": 1, "title": "Ä"}\n{"id": 2}')
    monkeypatch.setattr(discogs_api, "search", lambda *a: [])
    assert await call("discogs_search", q="x") == (False, "(nothing)")


async def test_errors_come_back_as_tool_errors(monkeypatch):
    def boom(*a):
        raise RuntimeError("Browser not running on http://127.0.0.1:9222 and autostart is off.")

    monkeypatch.setattr(discogs_api, "release", boom)
    err, text = await call("discogs_release", release_id=1)
    assert err and "autostart is off" in text
