"""Manual test without MCP:  uv run ochi-try <url>   or   uv run ochi-try --snapshot <url>"""
from __future__ import annotations

import asyncio
import sys
from . import browser, config, extractors


def main() -> None:
    # extractor output has emoji; Windows consoles default to a legacy code page
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if not args or (args[0] == "--snapshot" and len(args) < 2):
        print(__doc__)
        sys.exit(1)
    if args[0] == "--snapshot":
        path = asyncio.run(browser.snapshot(args[1], config.ROOT / "snapshots"))
        print(f"saved {path}")
        return
    url = args[0]
    ex = extractors.find(url)
    if ex is None:
        sys.exit("No extractor available (extractors/ folder empty?).")
    print(f"[extractor: {ex.name}]")
    result = asyncio.run(browser.run(url, ex))
    print(browser.to_text(result, 200000))


if __name__ == "__main__":
    main()
