"""chrome.ensure() really starts a browser with ochi's flags, on every OS (headless, temp profile, free port)."""
from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from ochi import chrome, config

pytestmark = [pytest.mark.anyio, pytest.mark.browser]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def test_ensure_launches_and_reuses_browser(tmp_path, monkeypatch):
    async with async_playwright() as p:
        exe = p.chromium.executable_path
    if not Path(exe).exists():
        exe = config.find_chrome()
    if not exe:
        pytest.skip("no Chromium: run `uv run playwright install chromium`")

    port = free_port()
    toml = tmp_path / "ochi.toml"
    args = ["--headless=new", "--no-first-run", "--no-default-browser-check"]
    if sys.platform.startswith("linux"):
        # CI runners (Ubuntu 24.04 AppArmor) don't let a downloaded Chromium set up its sandbox;
        # Playwright's own launch() passes this flag by default for the same reason
        args.append("--no-sandbox")
    # TOML literal strings ('...'): Windows paths keep their backslashes
    toml.write_text(
        f"[chrome]\npath = '{exe}'\nprofile = '{tmp_path / 'profile'}'\nport = {port}\n"
        f"args = {json.dumps(args)}\n",  # a JSON list of strings is a valid TOML array
        encoding="utf-8")
    monkeypatch.setenv("OCHI_CONFIG", str(toml))
    config.load.cache_clear()

    assert chrome.version() is None
    info = await chrome.ensure(timeout_s=30)
    try:
        assert "Browser" in info
        assert chrome.version() is not None
        assert await chrome.ensure() == info  # already up: no second launch
        assert (tmp_path / "profile").is_dir()
    finally:
        async with async_playwright() as p:
            b = await p.chromium.connect_over_cdp(chrome.cdp_url())
            cdp = await b.new_browser_cdp_session()
            try:
                await cdp.send("Browser.close")
            except Exception:  # noqa: BLE001  (the connection drops as the browser exits)
                pass


async def test_ensure_without_autostart_fails_fast(tmp_path, monkeypatch):
    toml = tmp_path / "ochi.toml"
    toml.write_text(f"[chrome]\nport = {free_port()}\nautostart = false\n", encoding="utf-8")
    monkeypatch.setenv("OCHI_CONFIG", str(toml))
    config.load.cache_clear()
    with pytest.raises(RuntimeError, match="autostart is off"):
        await chrome.ensure()


async def test_ensure_reports_a_browser_that_dies_at_start(tmp_path, monkeypatch):
    # Python rejects Chrome's flags and exits with code 2 at once: stands in for a crashing browser
    toml = tmp_path / "ochi.toml"
    toml.write_text(f"[chrome]\npath = '{sys.executable}'\nport = {free_port()}\nargs = []\n", encoding="utf-8")
    monkeypatch.setenv("OCHI_CONFIG", str(toml))
    config.load.cache_clear()
    with pytest.raises(RuntimeError, match="exited with code 2"):
        await chrome.ensure(timeout_s=10)


def test_launch_without_browser_explains(monkeypatch):
    monkeypatch.setattr(config, "find_chrome", lambda: None)
    with pytest.raises(RuntimeError, match="OCHI_CHROME"):
        chrome.launch()
