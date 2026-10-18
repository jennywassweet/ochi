"""Extractors run in a real headless Chromium against saved fixtures; no network.

Uses Playwright's own Chromium if installed (`uv run playwright install chromium`),
otherwise an installed Chrome; skipped when neither is available.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from ochi import extractors
from ochi.browser import wrap

pytestmark = pytest.mark.browser

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        for kwargs in ({}, {"channel": "chrome"}):
            try:
                b = p.chromium.launch(**kwargs)
                break
            except PlaywrightError:
                continue
        else:
            pytest.skip("no Chromium: run `uv run playwright install chromium`")
        yield b
        b.close()


@pytest.fixture
def site(browser):
    """A page whose network is answered only by `routes` (url regex -> (content_type, body | callable))."""
    context = browser.new_context()
    routes, requests = [], []

    def handle(route):
        url = route.request.url
        requests.append(url)
        for pattern, ctype, body in routes:
            if re.search(pattern, url):
                return route.fulfill(status=200, content_type=ctype, body=body(url) if callable(body) else body)
        return route.fulfill(status=404, body="not found")

    context.route("**/*", handle)
    page = context.new_page()
    page.routes, page.requests = routes, requests
    yield page
    context.close()


def run(page, url):
    page.goto(url)
    return page.evaluate(wrap(extractors.find(url).code))


HTML = "text/html; charset=utf-8"
JSON = "application/json"


def test_generic_keeps_main_text_and_drops_chrome(site):
    site.routes.append(("example.test", HTML, """<html><head><title>Hello</title></head><body>
        <nav>Menu Home About</nav><article><h1>Head line</h1><p>First   para.</p><script>var x=1</script>
        <aside>Ad</aside><p>Second para.</p></article><footer>Footer text</footer></body></html>"""))
    text = run(site, "https://example.test/post")
    assert text.splitlines()[:3] == ["# Hello", "https://example.test/post", ""]
    assert "Head line" in text and "First para." in text and "Second para." in text
    for junk in ("Menu", "Ad", "Footer", "var x"):
        assert junk not in text


def test_reddit_thread(site):
    site.routes += [(r"\.json", JSON, (FIXTURES / "reddit-thread.json").read_text(encoding="utf-8")),
                    ("reddit.com", HTML, "<html><body>thread</body></html>")]
    lines = run(site, "https://www.reddit.com/r/vinyl/comments/abc/best_pressing/").splitlines()
    assert lines == [
        "# Best pressing of Dark Side?",
        "r/vinyl · u/op_user · 42 pts · 3 comments",
        "",
        "## Comments",
        "- [10] u/alice: The 1973 UK first press. No doubt.",
        "  - [3] u/bob: Agreed",
        "- [1] u/carol: The 2016 remaster",
    ]


def test_reddit_sub(site):
    site.routes += [(r"\.json", JSON, (FIXTURES / "reddit-sub.json").read_text(encoding="utf-8")),
                    ("reddit.com", HTML, "<html><body>sub</body></html>")]
    lines = run(site, "https://www.reddit.com/r/vinyl/new/?t=week").splitlines()
    assert lines[0] == "# r/vinyl — https://www.reddit.com/r/vinyl/new/?t=week"
    assert lines[1].startswith("- 📌 [Meta] Weekly thread · 5↑ 100💬 ")
    assert lines[1].endswith("· https://reddit.com/r/vinyl/comments/1/weekly/ — Post your hauls here")
    assert re.fullmatch(r"- Look at this \(i\.redd\.it\) · 99↑ 7💬 \d+h · https://reddit\.com/r/vinyl/comments/2/look/",
                        lines[2])
    assert any("/r/vinyl/new.json?limit=40&raw_json=1&t=week" in u for u in site.requests)


SELLER = "https://www.discogs.com/seller/shopper/profile?format=Vinyl&ochi_pages=1"


@pytest.fixture
def seller(site):
    site.routes.append(("discogs.com/seller/", HTML, (FIXTURES / "discogs-seller.html").read_text(encoding="utf-8")))
    return lambda params="": run(site, SELLER + params)


def test_discogs_seller_table(seller):
    r = seller("&ochi_max=20")
    assert r["total_on_site"] == "1,204"
    assert r["fetched"] == 4 and r["shown"] == 3 and r["filters"] == {"max_price": 20}  # €1,234.50 is over
    assert r["common"] == {"seller": "shopper", "rating": "99.6%", "from": "Netherlands", "shipping": "+€14.00"}
    assert r["items"][0] == {"id": "101", "title": "Artist A - First LP (LP, Album)", "label": "Lab One · L-1",
                             "media": "Very Good Plus (VG+)", "sleeve": "Very Good (VG)", "price": "€12.50",
                             "total": 26.5}
    assert r["items"][1]["price"] == "8,99 €" and r["items"][1]["total"] == 22.99
    assert "ochi_" not in r["url"] and "limit=250" in r["url"]


def ids(r):
    return [i["id"] for i in r["items"]]


@pytest.mark.parametrize(("params", "expected"), [
    ("", ["101", "102", "103", "104"]),
    ("&ochi_min_media=NM", ["102", "103"]),            # M and NM pass, VG+ and G+ don't
    ("&ochi_min_media=vg%2B", ["101", "102", "103"]),  # case-insensitive, "+" URL-encoded
    ("&ochi_min_sleeve=VG", ["101", "102", "103"]),    # a Generic sleeve has no grade
    ("&ochi_max_total=25", ["102", "104"]),            # 8.99+14, 3+14; 12.50+14 is 26.50
    ("&ochi_sort=price", ["104", "102", "101", "103"]),
    ("&ochi_sort=total&ochi_min_media=VG", ["102", "101", "103"]),
])
def test_discogs_filters(seller, params, expected):
    assert ids(seller(params)) == expected


def test_discogs_fields(seller):
    r = seller("&ochi_fields=price,media&ochi_max=10")
    assert r["items"] == [{"id": "102", "media": "Mint (M)", "price": "8,99 €"},
                          {"id": "104", "media": "Good Plus (G+)", "price": "€3.00"}]


@pytest.mark.parametrize("params", ["&ochi_min_media=excellent", "&ochi_sort=rating"])
def test_discogs_bad_filter_is_reported(seller, params):
    assert "error" in seller(params)


def test_discogs_shop_list_graphql(site):
    data = json.loads((FIXTURES / "discogs-shop-list.graphql.json").read_text(encoding="utf-8"))
    edges = data["data"]["marketplaceSearch"]["edges"]
    graphql_vars = []

    def graphql(url):
        graphql_vars.append(json.loads(parse_qs(urlsplit(url).query)["variables"][0]))
        return json.dumps(data)

    # the real page is a React app that fires this query itself; stand in for it with a tiny script
    page_html = """<html><body><div class="msr-results-footer">1 – 25</div><script>
        fetch('/graphql?operationName=MarketplaceSearch&variables='
              + encodeURIComponent(JSON.stringify({first: 25, filters: {genre: ['Rock']}})));
        </script></body></html>"""
    site.routes += [("/graphql", JSON, graphql), ("discogs.com/shop/", HTML, page_html)]
    r = run(site, "https://www.discogs.com/shop/list?genre=Rock&formatName=Vinyl&ochi_max=20&ochi_pages=1")

    assert graphql_vars[-1] == {"first": 250, "filters": {"genre": ["Rock"]}}  # page's filters kept, size raised
    assert r["total_on_site"] == data["data"]["marketplaceSearch"]["totalCount"]
    assert r["fetched"] == len(edges)
    cheap = [e["node"] for e in edges if (e["node"].get("buyerPrice") or e["node"]["price"])["amount"] <= 20]
    assert r["shown"] == len(cheap) > 0
    first = next(i for i in r["items"] if i["id"] == str(cheap[0]["id"]))
    assert re.fullmatch(r"€\d+\.\d\d", first["price"])
    assert " - " in first["title"]


def test_discogs_shop_list_filters(site):
    data = json.loads((FIXTURES / "discogs-shop-list.graphql.json").read_text(encoding="utf-8"))
    nodes = [e["node"] for e in data["data"]["marketplaceSearch"]["edges"]]
    page_html = """<html><body><script>
        fetch('/graphql?operationName=MarketplaceSearch&variables=' + encodeURIComponent('{"first":25}'));
        </script></body></html>"""
    site.routes += [("/graphql", JSON, json.dumps(data)), ("discogs.com/shop/", HTML, page_html)]
    r = run(site, "https://www.discogs.com/shop/list?ochi_pages=1&ochi_min_media=NM&ochi_sort=total")

    good = [n for n in nodes if n["mediaCondition"] in ("MINT", "NEAR_MINT")]
    assert r["shown"] == len(good) > 0
    totals = [i.get("total", 0) for i in r["items"]]
    assert totals == sorted(totals)
    for item in r["items"]:
        assert item.get("media", r["common"].get("media")) in ("Mint (M)", "Near Mint (NM or M-)")


def test_discogs_release_sellers_in_buyer_currency(site):
    """Real page (anonymized): sellers in EUR and USD; totals use Discogs' conversion to the buyer's currency."""
    html = (FIXTURES / "discogs-release-sellers.html").read_text(encoding="utf-8")
    site.routes.append(("discogs.com/sell/release/", HTML, html))
    r = run(site, "https://www.discogs.com/sell/release/13844130?ochi_pages=1&ochi_sort=total")
    assert r["fetched"] == 10 and r["total_on_site"] == "10"
    items = r["items"]
    usd = next(i for i in items if i["id"] == "4410581886")
    assert (usd["price"], usd["shipping"], usd["total"]) == ("$30.00", "+$15.00", 40.05)
    assert usd["from"] == "United Arab Emirates" and usd["free_over"] == "$1,000.00"
    known = [i["total"] for i in items if "total" in i]
    assert known == sorted(known) and len(known) == 8
    assert [i["shipping"] for i in items[-2:]] == ["?", "?"]  # unknown shipping sorts last
    assert all(i.get("from") for i in items)

    cheap = run(site, "https://www.discogs.com/sell/release/13844130?ochi_pages=1&ochi_max=41")
    # $44.99 is about €40.04 for the buyer, so it passes a 41 (EUR) limit; €45.00 doesn't
    assert {"4413292671", "4410581886"} <= {i["id"] for i in cheap["items"]}
    assert "3248375315" not in {i["id"] for i in cheap["items"]}
