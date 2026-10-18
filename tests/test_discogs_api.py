from __future__ import annotations

import io
import json
import urllib.parse

import pytest

from ochi import discogs_api


@pytest.fixture
def fake_get(monkeypatch):
    calls, responses = [], {}

    def _get(path, **params):
        calls.append((path, params))
        return responses[path]

    monkeypatch.setattr(discogs_api, "_get", _get)
    return calls, responses


def test_get_builds_url_and_auth(monkeypatch):
    seen = {}

    def urlopen(req, timeout):
        seen["url"], seen["headers"] = req.full_url, dict(req.header_items())
        return io.BytesIO(json.dumps({"ok": True}).encode())

    monkeypatch.setattr(discogs_api.urllib.request, "urlopen", urlopen)
    monkeypatch.setenv("DISCOGS_TOKEN", "t0k")
    assert discogs_api._get("/database/search", q="a b", format="", type=None) == {"ok": True}
    url = urllib.parse.urlsplit(seen["url"])
    assert url.path == "/database/search"
    assert urllib.parse.parse_qs(url.query) == {"q": ["a b"]}  # empty params dropped
    assert seen["headers"]["Authorization"] == "Discogs token=t0k"
    assert seen["headers"]["User-agent"].startswith("ochi/")


def test_get_without_token_sends_no_auth(monkeypatch):
    seen = {}

    def urlopen(req, timeout):
        seen["headers"] = dict(req.header_items())
        return io.BytesIO(b"{}")

    monkeypatch.setattr(discogs_api.urllib.request, "urlopen", urlopen)
    discogs_api._get("/x")
    assert "Authorization" not in seen["headers"]


def test_search(fake_get):
    calls, responses = fake_get
    responses["/database/search"] = {"results": [
        {"id": 1, "type": "release", "title": "A - B", "year": "1999", "country": "", "format": ["Vinyl", "LP"],
         "label": ["L1", "L1", "L2"], "style": ["Dub"]},
    ]}
    assert discogs_api.search("a", format="Vinyl", per_page=5) == [
        {"id": 1, "type": "release", "title": "A - B", "year": "1999",
         "format": "Vinyl, LP", "label": "L1, L2", "style": "Dub"},
    ]
    assert calls == [("/database/search", {"q": "a", "type": "release", "format": "Vinyl", "per_page": 5})]


def test_release(fake_get):
    _, responses = fake_get
    responses["/releases/7"] = {
        "id": 7, "title": "LP", "year": 1970, "country": "UK", "artists": [{"name": "X"}, {"name": "Y"}],
        "labels": [{"name": "Lab", "catno": "C1"}, {"name": "NoCat"}],
        "formats": [{"qty": "1", "name": "Vinyl", "descriptions": ["LP", "Album"]}],
        "tracklist": [{"position": "A1", "title": "Song", "duration": "3:00"}, {"title": "Hidden"}],
        "community": {"have": 10, "want": 20}, "lowest_price": 12.5, "num_for_sale": 3,
        "uri": "https://www.discogs.com/release/7",
    }
    r = discogs_api.release(7)
    assert r["title"] == "X, Y – LP"
    assert r["labels"] == ["Lab C1", "NoCat"]
    assert r["formats"] == ["1×Vinyl LP, Album"]
    assert r["tracklist"] == ["A1 Song 3:00", "Hidden"]
    assert r["have_want"] == "10/20"
    assert r["lowest_price_eur"] == 12.5


def test_master_versions_tolerates_missing_stats(fake_get):
    _, responses = fake_get
    responses["/masters/5/versions"] = {"versions": [
        {"id": 1, "label": "L", "stats": {"community": {"in_collection": 3, "in_wantlist": 4}}},
        {"id": 2},
    ]}
    rows = discogs_api.master_versions(5)
    assert [r["have_want"] for r in rows] == ["3/4", "None/None"]


def test_listing(fake_get):
    _, responses = fake_get
    responses["/marketplace/listings/9"] = {
        "id": 9, "status": "For Sale", "condition": "Mint (M)", "sleeve_condition": "Near Mint (NM or M-)",
        "price": {"value": 20.0, "currency": "EUR"}, "shipping_price": {"value": 5.0},
        "release": {"description": "X - LP"}, "seller": {"username": "s", "stats": {"rating": "99.9", "total": 100}},
    }
    r = discogs_api.listing(9)
    assert (r["price"], r["shipping"], r["currency"], r["seller"], r["rating"]) == (20.0, 5.0, "EUR", "s", "99.9")


def http_error(code, body=b"{}", headers=None):
    import email.message
    msg = email.message.Message()
    for k, v in (headers or {}).items():
        msg[k] = v
    return discogs_api.urllib.error.HTTPError("https://api.discogs.com/x", code, "reason", msg, io.BytesIO(body))


def test_retries_on_rate_limit(monkeypatch):
    calls, sleeps = [], []

    def urlopen(req, timeout):
        calls.append(1)
        if len(calls) < 3:
            raise http_error(429, headers={"Retry-After": "1"} if len(calls) == 1 else None)
        return io.BytesIO(b'{"ok": 1}')

    monkeypatch.setattr(discogs_api.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(discogs_api.time, "sleep", sleeps.append)
    assert discogs_api._get("/x") == {"ok": 1}
    assert sleeps == [1.0, 4.0]  # Retry-After, then backoff for the 2nd attempt


def test_gives_up_after_retries(monkeypatch):
    def urlopen(req, timeout):
        raise http_error(429)

    monkeypatch.setattr(discogs_api.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(discogs_api.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="rate limit still hit"):
        discogs_api._get("/x")


@pytest.mark.parametrize(("code", "token", "msg"), [
    (401, None, "needs a token"),
    (401, "bad", "DISCOGS_TOKEN looks wrong"),
    (404, None, "not found"),
    (500, None, "HTTP 500 Server broke"),
])
def test_errors_are_explained(monkeypatch, code, token, msg):
    if token:
        monkeypatch.setenv("DISCOGS_TOKEN", token)

    def urlopen(req, timeout):
        raise http_error(code, body=b'{"message": "Server broke"}')

    monkeypatch.setattr(discogs_api.urllib.request, "urlopen", urlopen)
    with pytest.raises(RuntimeError, match=msg):
        discogs_api._get("/releases/1")


def test_network_errors_are_explained(monkeypatch):
    def urlopen(req, timeout):
        raise discogs_api.urllib.error.URLError("nodename nor servname provided")

    monkeypatch.setattr(discogs_api.urllib.request, "urlopen", urlopen)
    with pytest.raises(RuntimeError, match="Can't reach the Discogs API"):
        discogs_api._get("/x")
