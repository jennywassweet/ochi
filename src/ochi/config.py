"""ochi.toml + .env loading. Env vars override the file (OCHI_CHROME, OCHI_PROFILE, OCHI_PORT)."""
from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@lru_cache
def load() -> dict:
    cfg: dict = {}
    path = Path(os.environ.get("OCHI_CONFIG", ROOT / "ochi.toml"))
    if path.exists():
        cfg = tomllib.loads(path.read_text(encoding="utf-8"))
    chrome = cfg.setdefault("chrome", {})
    chrome.setdefault("path", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    chrome.setdefault("profile", "~/.ochi-profile")
    chrome.setdefault("port", 9222)
    chrome.setdefault("autostart", True)
    chrome.setdefault("args", ["--no-first-run", "--no-default-browser-check"])
    if v := os.environ.get("OCHI_CHROME"):
        chrome["path"] = v
    if v := os.environ.get("OCHI_PROFILE"):
        chrome["profile"] = v
    if v := os.environ.get("OCHI_PORT"):
        chrome["port"] = int(v)
    return cfg


def load_dotenv() -> None:
    """Minimal .env reader (KEY=VALUE lines) into os.environ, without overriding."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
