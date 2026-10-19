from __future__ import annotations

import io
import json
import urllib.parse
from pathlib import Path

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


def shipping_fixture(kind):
    path = Path(__file__).parent / "fixtures" / f"discogs-shipping-{kind}.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def shipping_api(fake_get):
    calls, responses = fake_get
    responses["/users/someone"] = {"id": 42, "username": "someone"}

    def use(kind):
        responses["/v3/marketplace/shipping/policies"] = shipping_fixture(kind)
        return discogs_api.shipping("someone", "Germany")

    return calls, use


def test_shipping_by_quantity(shipping_api):
    calls, use = shipping_api
    r = use("quantity")
    assert calls[-1] == ("/v3/marketplace/shipping/policies", {"seller_id": 42, "country": "Germany"})
    assert (r["seller"], r["country"], r["currency"], r["ships"]) == ("someone", "Germany", "EUR", True)
    assert "free_shipping_from" not in r
    lp = next(m for m in r["methods"] if any("Vinyl (Large)" in x for x in m.get("rates", [])))
    assert lp["by"] == "quantity" and lp["days"]
    assert lp["rates"] == ["1 - 1 Vinyl (Large): €20.00", "2 and up Vinyl (Large): €2.00 per each additional 1 item"]


def test_shipping_by_weight(shipping_api):
    _, use = shipping_api
    r = use("weight")
    assert {m["by"] for m in r["methods"]} == {"weight"}
    assert "501 and up grams: €2.00 per each additional 200 grams" in r["methods"][0]["rates"]


def test_shipping_free_threshold_and_rate_less_methods(shipping_api):
    _, use = shipping_api
    r = use("free")
    assert r["currency"] == "USD" and r["free_shipping_from"] == "$1,000.00"
    by_name = {m["name"]: m for m in r["methods"]}
    assert by_name["Standard - Local Mail"]["rates"][0] == "1 - 3 items: $15.00"
    assert by_name["Free Shipping"] == {"name": "Free Shipping", "min_order": "$1,000.00"}
    assert by_name["Local Pickup"] == {"name": "Local Pickup"}


def test_shipping_not_to_this_country(shipping_api):
    _, use = shipping_api
    r = use("none")
    assert r["ships"] is False and "doesn't ship" in r["note"] and "methods" not in r


def test_shipping_is_a_single_read_only_request_to_the_api(monkeypatch):
    """Two GETs to api.discogs.com (user lookup, policies), with the token and no cookies: nothing touches a cart."""
    seen = []

    def urlopen(req, timeout):
        seen.append((req.get_method(), urllib.parse.urlsplit(req.full_url), dict(req.header_items())))
        body = {"id": 42} if "/users/" in req.full_url else shipping_fixture("quantity")
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr(discogs_api.urllib.request, "urlopen", urlopen)
    monkeypatch.setenv("DISCOGS_TOKEN", "t0k")
    discogs_api.shipping("someone", "Germany")
    assert [(m, u.netloc, u.path) for m, u, _ in seen] == [
        ("GET", "api.discogs.com", "/users/someone"),
        ("GET", "api.discogs.com", "/v3/marketplace/shipping/policies"),
    ]
    for _, _, headers in seen:
        assert headers["Authorization"] == "Discogs token=t0k"
        assert "Cookie" not in headers


def info(i, artist, title, style, fmt="LP"):
    return {"id": i, "title": title, "year": 1970 + i, "artists": [{"name": artist}],
            "labels": [{"name": "Lab", "catno": f"L-{i}"}, {"name": "Lab", "catno": f"L-{i}"}],
            "formats": [{"name": "Vinyl", "qty": "1", "descriptions": [fmt, "Album"]}],
            "styles": [style], "genres": ["Rock"], "master_id": 0}


@pytest.fixture
def account(fake_get):
    calls, responses = fake_get
    responses["/oauth/identity"] = {"username": "me"}

    # /wants: two pages, 100 + 1 entries
    pages = {1: [{"basic_information": info(i, "Band", f"T{i}", "Psychedelic Rock" if i % 2 else "Doom Metal"),
                  "date_added": "2026-01-02T03:04:05-07:00", "notes": "first press!" if i == 1 else ""}
                 for i in range(1, 101)],
             2: [{"basic_information": info(101, "Other", "Last", "Krautrock", fmt="7\""),
                  "date_added": "2026-02-02T00:00:00-07:00", "notes": ""}]}

    def get(path, **params):
        calls.append((path, params))
        if path == "/users/me/wants":
            assert params["per_page"] == 100
            return {"pagination": {"pages": 2}, "wants": pages[params["page"]]}
        if path == "/users/me/collection/folders/0/releases":
            return {"pagination": {"pages": 1}, "releases": [
                {"basic_information": info(5, "Owned", "Record", "Jazz"), "date_added": "2025-05-05", "rating": 4},
                {"basic_information": info(6, "Owned", "Unrated", "Jazz"), "date_added": "2025-05-06", "rating": 0},
            ]}
        return responses[path]

    import ochi.discogs_api as api
    return calls, get, api


def test_wantlist_of_token_owner_all_pages(account, monkeypatch):
    calls, get, api = account
    monkeypatch.setattr(api, "_get", get)
    rows = api.wantlist()
    assert calls[0] == ("/oauth/identity", {})
    assert len(rows) == 101
    assert rows[0] == {"release_id": 1, "title": "Band – T1", "year": 1971, "format": "1×Vinyl LP, Album",
                       "label": "Lab L-1", "styles": "Psychedelic Rock", "added": "2026-01-02", "notes": "first press!"}
    assert rows[-1]["format"] == '1×Vinyl 7", Album'


def test_wantlist_query_and_limit(account, monkeypatch):
    _, get, api = account
    monkeypatch.setattr(api, "_get", get)
    psych = api.wantlist(query="PSYCHEDELIC")
    assert len(psych) == 50 and all("Psychedelic" in r["styles"] for r in psych)
    assert [r["release_id"] for r in api.wantlist(query='7"')] == [101]
    assert len(api.wantlist(limit=3)) == 3


def test_wantlist_of_another_user_skips_identity(account, monkeypatch):
    calls, get, api = account

    def other(path, **params):
        calls.append((path, params))
        return {"pagination": {"pages": 1}, "wants": []}

    monkeypatch.setattr(api, "_get", other)
    assert api.wantlist("some one") == []
    assert calls == [("/users/some%20one/wants", {"per_page": 100, "page": 1})]


def test_collection(account, monkeypatch):
    _, get, api = account
    monkeypatch.setattr(api, "_get", get)
    rows = api.collection()
    assert rows[0]["title"] == "Owned – Record" and rows[0]["rating"] == 4 and rows[0]["added"] == "2025-05-05"
    assert "rating" not in rows[1]
