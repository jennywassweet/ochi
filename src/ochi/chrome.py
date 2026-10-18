"""Starting / checking the ochi Chrome instance."""
from __future__ import annotations

import asyncio
import json
import subprocess
import urllib.request
from pathlib import Path

from . import config


def cdp_url() -> str:
    return f"http://127.0.0.1:{config.load()['chrome']['port']}"


def version() -> dict | None:
    """Browser info if the debugging port answers, else None."""
    try:
        with urllib.request.urlopen(cdp_url() + "/json/version", timeout=1) as r:
            return json.load(r)
    except Exception:  # noqa: BLE001
        return None


def launch() -> subprocess.Popen:
    c = config.load()["chrome"]
    if not c["path"]:
        raise RuntimeError("No Chrome/Chromium/Brave/Edge found; set [chrome].path in ochi.toml "
                           "or OCHI_CHROME")
    exe = Path(c["path"]).expanduser()
    if not exe.exists():
        raise RuntimeError(f"Browser binary not found: {exe} (set [chrome].path in ochi.toml)")
    profile = Path(c["profile"]).expanduser()
    cmd = [str(exe), f"--remote-debugging-port={c['port']}", f"--user-data-dir={profile}", *c["args"]]
    # detached: survives ochi restarts, logs go nowhere
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            stdin=subprocess.DEVNULL, start_new_session=True)


async def ensure(timeout_s: float = 15) -> dict:
    """Make sure the browser is up; start it if allowed. Returns /json/version info."""
    if info := version():
        return info
    if not config.load()["chrome"]["autostart"]:
        raise RuntimeError(f"Browser not running on {cdp_url()} and autostart is off.")
    proc = launch()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        await asyncio.sleep(0.5)
        if info := version():
            return info
        if (code := proc.poll()) is not None:
            hint = ("is this profile already open without the debugging port?" if code == 0 else
                    "try running it by hand with the same flags to see why")
            raise RuntimeError(f"The browser exited with code {code} before {cdp_url()} answered ({hint}).")
    raise RuntimeError(f"Started the browser but {cdp_url()} did not answer within {timeout_s}s.")
