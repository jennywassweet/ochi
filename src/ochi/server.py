"""ochi MCP server: fetch(url) through the user's Chrome using per-site extractors, plus a bit of Discogs API."""
from __future__ import annotations

import asyncio
import json
import sys

from mcp.server.fastmcp import FastMCP

from . import browser, chrome, config, discogs_api, extractors

mcp = FastMCP("ochi")


def _j(x) -> str:
    if isinstance(x, list):
        return "\n".join(json.dumps(r, ensure_ascii=False) for r in x) or "(nothing)"
    return json.dumps(x, ensure_ascii=False, indent=1)


# ---------- browser ----------

@mcp.tool()
async def fetch(url: str, max_chars: int = 40000) -> str:
    """Read a web page through the user's own Chrome (started automatically if needed).

    A site-specific extractor (if one matches the URL) returns clean structured data;
    otherwise a generic extractor returns the readable text of the page.
    Use for sites that block normal fetching (Discogs marketplace, Reddit, news).
    Discogs marketplace URLs accept ochi_max=<price> to keep only cheaper items.
    """
    ex = extractors.find(url)
    if ex is None:
        return "No extractor available (extractors/ folder empty?)."
    result = await browser.run(url, ex)
    return f"[extractor: {ex.name}]\n" + browser.to_text(result, max_chars)


@mcp.tool()
async def look(tab: int | None = None, max_chars: int = 40000) -> str:
    """Read the page the user is looking at right now in the ochi browser (the visible tab),
    or tab number `tab` from tabs(). Does not navigate or close anything."""
    url, name, result = await browser.look(tab, extractors.find)
    return f"[tab: {url}] [extractor: {name}]\n" + browser.to_text(result, max_chars)


@mcp.tool()
async def show(url: str) -> str:
    """Open a page for the user in a new visible tab of the ochi browser and leave it open
    ("look what I found"). Use sparingly: only when they'd want to see it themselves."""
    title = await browser.show(url)
    return f"Opened: {title} — {url}"


@mcp.tool()
async def tabs() -> str:
    """List open tabs in the ochi browser (index, title, url, which one is visible)."""
    return _j(await browser.tabs())


@mcp.tool()
async def browser_start() -> str:
    """Start the ochi Chrome (separate profile) if it isn't running; report its version."""
    info = await chrome.ensure()
    return f"Browser up on {chrome.cdp_url()}: {info.get('Browser')}"


@mcp.tool()
def browser_status() -> str:
    """Is the ochi Chrome running? (does not start it)"""
    info = chrome.version()
    return f"running: {info.get('Browser')}" if info else "not running"


@mcp.tool()
def list_extractors() -> str:
    """List the site extractors ochi knows, with their URL patterns."""
    rows = [f"- {ex.name}: {', '.join(ex.matches)}  {ex.description}" for ex in extractors.load_all()]
    return "\n".join(rows) or "No extractors."


@mcp.tool()
async def snapshot(url: str) -> str:
    """Save the rendered HTML of a page into snapshots/ (to write or debug an extractor)."""
    path = await browser.snapshot(url, config.home() / "snapshots")
    return f"Saved {path} ({path.stat().st_size} bytes)"


# ---------- Discogs API (structured data, no browser needed) ----------

@mcp.tool()
async def discogs_search(q: str, type: str = "release", format: str = "", per_page: int = 15) -> str:
    """Search the Discogs database. type: release | master | artist | label. format e.g. Vinyl."""
    return _j(await asyncio.to_thread(discogs_api.search, q, type, format, per_page))


@mcp.tool()
async def discogs_release(release_id: int) -> str:
    """Release details: labels, formats, styles, tracklist, master_id, lowest price (EUR), have/want."""
    return _j(await asyncio.to_thread(discogs_api.release, release_id))


@mcp.tool()
async def discogs_master_versions(master_id: int, format: str = "Vinyl") -> str:
    """All pressings of a master release (filter by format)."""
    return _j(await asyncio.to_thread(discogs_api.master_versions, master_id, format))


@mcp.tool()
async def discogs_listing(listing_id: int) -> str:
    """One marketplace listing: price, shipping to the logged-in user, seller rating, comments."""
    return _j(await asyncio.to_thread(discogs_api.listing, listing_id))


def main() -> None:
    """`ochi` runs the MCP server on stdio; `ochi init` sets up the config folder."""
    if sys.argv[1:2] == ["init"]:
        from .cli import init
        init()
        return
    config.load_dotenv()
    mcp.run()


if __name__ == "__main__":
    main()
