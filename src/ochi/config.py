"""Where ochi keeps its files, ochi.toml + .env loading.

Env vars override the file (OCHI_CHROME, OCHI_PROFILE, OCHI_PORT); OCHI_HOME / OCHI_CONFIG move the files.
"""
from __future__ import annotations

import os
import shutil
import sys
import tomllib
from functools import lru_cache
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
CHECKOUT = PACKAGE.parents[1]  # the repo root when running from a source checkout


def from_checkout() -> bool:
    return (CHECKOUT / "pyproject.toml").is_file() and (CHECKOUT / "src" / "ochi").is_dir()


def user_dir() -> Path:
    """The per-user config folder: ~/Library/Application Support/ochi, %APPDATA%\\ochi, ~/.config/ochi."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "ochi"


def home() -> Path:
    """Folder with ochi.toml, .env, extra extractors/ and snapshots/: OCHI_HOME, else the source
    checkout when running from one, else the per-user config folder (installed with uvx / pip)."""
    if v := os.environ.get("OCHI_HOME"):
        return Path(v).expanduser()
    return CHECKOUT if from_checkout() else user_dir()


def bundled(name: str) -> Path:
    """A file shipped with ochi (extractors, examples): inside the wheel, or at the checkout root."""
    inside = PACKAGE / "data" / name.lstrip(".")
    return inside if inside.exists() else CHECKOUT / name

_MAC_APPS = ["Google Chrome", "Chromium", "Brave Browser", "Microsoft Edge"]
_WIN_APPS = ["Google/Chrome/Application/chrome.exe", "Chromium/Application/chrome.exe",
             "BraveSoftware/Brave-Browser/Application/brave.exe", "Microsoft/Edge/Application/msedge.exe"]
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
    path = Path(os.environ.get("OCHI_CONFIG") or home() / "ochi.toml")
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
    urls = cfg.setdefault("urls", {})
    urls.setdefault("allow", [])
    urls.setdefault("deny", [])
    urls.setdefault("allow_private", False)
    return cfg


def load_dotenv() -> None:
    """Minimal .env reader (KEY=VALUE lines) into os.environ, without overriding."""
    path = home() / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
