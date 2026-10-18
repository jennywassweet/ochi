"""ochi MCP server: fetch(url) through the user's Chrome using per-site extractors."""
from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import browser, extractors

mcp = FastMCP("ochi")


@mcp.tool()
async def fetch(url: str, max_chars: int = 40000) -> str:
    """Read a web page through the user's own Chrome.

    A site-specific extractor (if one matches the URL) returns clean structured data;
    otherwise a generic extractor returns the readable text of the page.
    Use for sites that block normal fetching (Discogs marketplace, Reddit, news).
    """
    ex = extractors.find(url)
    if ex is None:
        return "No extractor available (extractors/ folder empty?)."
    result = await browser.run(url, ex)
    return f"[extractor: {ex.name}]\n" + browser.to_text(result, max_chars)


@mcp.tool()
def list_extractors() -> str:
    """List the site extractors ochi knows, with their URL patterns."""
    rows = []
    for ex in extractors.load_all():
        rows.append(f"- {ex.name}: {', '.join(ex.matches)}  {ex.description}")
    return "\n".join(rows) or "No extractors."


@mcp.tool()
async def snapshot(url: str) -> str:
    """Save the rendered HTML of a page into snapshots/ (to write or debug an extractor)."""
    out = Path(__file__).resolve().parents[2] / "snapshots"
    path = await browser.snapshot(url, out)
    return f"Saved {path} ({path.stat().st_size} bytes)"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
