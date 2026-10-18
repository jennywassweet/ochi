"""Manual test without MCP:  uv run ochi-try <url>   or   uv run ochi-try --snapshot <url>"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from . import browser, extractors


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    if args[0] == "--snapshot":
        path = asyncio.run(browser.snapshot(args[1], Path("snapshots")))
        print(f"saved {path}")
        return
    url = args[0]
    ex = extractors.find(url)
    print(f"[extractor: {ex.name if ex else None}]")
    result = asyncio.run(browser.run(url, ex))
    print(browser.to_text(result, 200000))


if __name__ == "__main__":
    main()
