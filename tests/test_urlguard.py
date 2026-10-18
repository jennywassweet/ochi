from __future__ import annotations

import pytest

from ochi import urlguard


def use_toml(tmp_path, monkeypatch, text):
    from ochi import config
    home = tmp_path / "ochi-home"
    home.mkdir(exist_ok=True)
    (home / "ochi.toml").write_text(text, encoding="utf-8")
    config.load.cache_clear()


@pytest.mark.parametrize("url", [
    "https://www.discogs.com/seller/x/profile",
    "http://example.com/",
    "https://8.8.8.8/",
    "https://[2001:4860:4860::8888]/",
])
def test_public_http_urls_pass(url):
    urlguard.check(url)


@pytest.mark.parametrize(("url", "msg"), [
    ("file:///etc/passwd", "only opens http"),
    ("chrome://settings", "only opens http"),
    ("javascript:alert(1)", "only opens http"),
    ("example.com", "only opens http"),
    ("http:///nohost", "No host"),
    ("http://localhost:8080/", "local/private"),
    ("http://app.localhost/", "local/private"),
    ("http://127.0.0.1/", "local/private"),
    ("http://[::1]/", "local/private"),
    ("http://192.168.1.1/admin", "local/private"),
    ("http://10.0.0.5/", "local/private"),
    ("http://169.254.169.254/latest/meta-data/", "local/private"),
    ("http://nas.local/", "local/private"),
])
def test_blocked_by_default(url, msg):
    with pytest.raises(ValueError, match=msg):
        urlguard.check(url)


def test_allow_private(tmp_path, monkeypatch):
    use_toml(tmp_path, monkeypatch, "[urls]\nallow_private = true\n")
    urlguard.check("http://localhost:3000/")
    urlguard.check("http://192.168.1.1/")


def test_allow_list_limits_and_permits_listed_private_hosts(tmp_path, monkeypatch):
    use_toml(tmp_path, monkeypatch, '[urls]\nallow = ["*.discogs.com", "localhost"]\n')
    urlguard.check("https://www.discogs.com/")
    urlguard.check("http://localhost:3000/")
    with pytest.raises(ValueError, match="not in \\[urls\\].allow"):
        urlguard.check("https://example.com/")
    with pytest.raises(ValueError, match="not in \\[urls\\].allow"):
        urlguard.check("http://192.168.1.1/")


def test_deny_wins(tmp_path, monkeypatch):
    use_toml(tmp_path, monkeypatch, '[urls]\nallow = ["*.example.com"]\ndeny = ["bank.example.com"]\n')
    urlguard.check("https://shop.example.com/")
    with pytest.raises(ValueError, match="deny"):
        urlguard.check("https://bank.example.com/")
