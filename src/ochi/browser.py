"""Talking to the user's own Chrome over CDP via Playwright."""
from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.async_api import async_playwright

from .extractors import Extractor

CDP = os.environ.get("OCHI_CDP", "http://localhost:9222")

CHROME_HINT = (
    "Chrome is not reachable at {cdp}. Start it with:\n"
    "/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome "
    "--remote-debugging-port=9222 --user-data-dir=$HOME/.ochi-profile"
)


async def run(url: str, extractor: Extractor, timeout_ms: int = 30000):
    """Open url in a new tab, run the extractor, close the tab, return its result."""
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(CDP)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(CHROME_HINT.format(cdp=CDP)) from e
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if extractor.wait:
                try:
                    await page.wait_for_selector(extractor.wait, timeout=timeout_ms)
                except Exception:  # noqa: BLE001
                    pass  # extractor gets a chance anyway; it reports what it sees
            # wrap the script so that it returns extract()'s result
            js = f"async () => {{\n{extractor.code}\nreturn await extract();\n}}"
            return await page.evaluate(js)
        finally:
            await page.close()
            # do NOT close the browser: it's the user's Chrome; just drop the connection


async def snapshot(url: str, out_dir: Path, timeout_ms: int = 30000) -> Path:
    """Save rendered HTML of a page, for writing new extractors and test fixtures."""
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(CDP)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(CHROME_HINT.format(cdp=CDP)) from e
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            html = await page.content()
        finally:
            await page.close()
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in url.split("://", 1)[-1])[:120]
    path = out_dir / f"{safe}.html"
    path.write_text(html, encoding="utf-8")
    return path


def to_text(result, max_chars: int) -> str:
    """Compact rendering for the model: rows as one line each, or plain text."""
    if isinstance(result, str):
        text = result
    elif isinstance(result, dict) and isinstance(result.get("items"), list):
        head = {k: v for k, v in result.items() if k != "items"}
        lines = [json.dumps(head, ensure_ascii=False)]
        lines += [json.dumps(r, ensure_ascii=False) for r in result["items"]]
        text = "\n".join(lines)
    elif isinstance(result, list):
        text = "\n".join(json.dumps(r, ensure_ascii=False) for r in result)
    else:
        text = json.dumps(result, ensure_ascii=False, indent=1)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n… [truncated, {len(text)} chars total]"
    return text
