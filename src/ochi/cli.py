"""Manual test without MCP:  ochi-try <url>   or   ochi-try --snapshot <url>"""
from __future__ import annotations

import asyncio
import shutil
import sys
from . import browser, config, extractors


def main() -> None:
    # extractor output has emoji; Windows consoles default to a legacy code page
    sys.stdout.reconfigure(encoding="utf-8")
    config.load_dotenv()
    args = sys.argv[1:]
    if not args or (args[0] == "--snapshot" and len(args) < 2):
        print(__doc__)
        sys.exit(1)
    if args[0] == "--snapshot":
        path = asyncio.run(browser.snapshot(args[1], config.home() / "snapshots"))
        print(f"saved {path}")
        return
    url = args[0]
    ex = extractors.find(url)
    if ex is None:
        sys.exit("No extractor available (extractors/ folder empty?).")
    print(f"[extractor: {ex.name}]")
    result = asyncio.run(browser.run(url, ex))
    print(browser.to_text(result, 200000))


def init() -> None:
    """Create ochi's home folder with ochi.toml, .env and extractors/ (existing files are kept)."""
    home = config.home()
    (home / "extractors").mkdir(parents=True, exist_ok=True)
    for example, target in (("ochi.example.toml", "ochi.toml"), (".env.example", ".env")):
        dest = home / target
        if dest.exists():
            print(f"kept     {dest}")
        else:
            shutil.copyfile(config.bundled(example), dest)
            print(f"created  {dest}")
    chrome = config.load()["chrome"]["path"]
    print(f"extractors of your own go to {home / 'extractors'} (same @name replaces a built-in one)")
    print(f"browser: {chrome or 'not found - set [chrome].path in ochi.toml'}")


if __name__ == "__main__":
    main()
