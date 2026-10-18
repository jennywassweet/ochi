"""ochi.toml + .env loading. Env vars override the file (OCHI_CHROME, OCHI_PROFILE, OCHI_PORT)."""
from __future__ import annotations

import os
import shutil
import sys
import tomllib
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_MAC_APPS = ["Google Chrome", "Chromium", "Brave Browser", "Microsoft Edge"]
_WIN_APPS = [r"Google\Chrome\Application\chrome.exe", r"Chromium\Application\chrome.exe",
             r"BraveSoftware\Brave-Browser\Application\brave.exe",
             r"Microsoft\Edge\Application\msedge.exe"]
_LINUX_CMDS = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
               "brave-browser", "microsoft-edge"]


def find_chrome() -> str | None:
    """First Chromium-based browser found in the usual places for this OS."""
    if sys.platform == "darwin":
        for app in _MAC_APPS:
            for base in (Path("/Applications"), Path.home() / "Applications"):
                exe = base / f"{app}.app" / "Contents" / "MacOS" / app
                if exe.exists():
                    return str(exe)
    elif sys.platform == "win32":
        for var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            if base := os.environ.get(var):
                for app in _WIN_APPS:
                    if (exe := Path(base) / app).exists():
                        return str(exe)
    for cmd in _LINUX_CMDS:
        if exe := shutil.which(cmd):
            return exe
    return None


@lru_cache
def load() -> dict:
    cfg: dict = {}
    path = Path(os.environ.get("OCHI_CONFIG", ROOT / "ochi.toml"))
    if path.exists():
        cfg = tomllib.loads(path.read_text(encoding="utf-8"))
    chrome = cfg.setdefault("chrome", {})
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
    if not chrome.get("path"):
        chrome["path"] = find_chrome()
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
