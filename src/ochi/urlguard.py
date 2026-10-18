"""Which URLs fetch/show/snapshot may open in the logged-in browser ([urls] in ochi.toml)."""
from __future__ import annotations

import fnmatch
import ipaddress
from urllib.parse import urlsplit

from . import config

_LOCAL_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa")


def is_private(host: str) -> bool:
    """localhost, local-network names and non-public IP addresses (routers, NAS, dev servers)."""
    if host == "localhost" or host.endswith(_LOCAL_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False  # a public-looking name; DNS answers are not checked
    return not ip.is_global


def check(url: str) -> None:
    """Raise ValueError if ochi should not open this URL."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ValueError(f"ochi only opens http(s) URLs, not {parts.scheme or 'this'}: {url}")
    host = (parts.hostname or "").rstrip(".")
    if not host:
        raise ValueError(f"No host in URL: {url}")
    rules = config.load()["urls"]
    if any(fnmatch.fnmatchcase(host, p) for p in rules["deny"]):
        raise ValueError(f"{host} is in [urls].deny in ochi.toml")
    allowed = any(fnmatch.fnmatchcase(host, p) for p in rules["allow"])
    if rules["allow"] and not allowed:
        raise ValueError(f"{host} is not in [urls].allow in ochi.toml")
    if is_private(host) and not (allowed or rules["allow_private"]):
        raise ValueError(f"{host} is a local/private address; set [urls].allow_private = true "
                         "(or list it in [urls].allow) in ochi.toml to open it")
