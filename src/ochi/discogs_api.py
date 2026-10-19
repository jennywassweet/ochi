"""The few Discogs API calls we actually use, compact outputs. Token: DISCOGS_TOKEN in .env."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.discogs.com"
UA = "ochi/0.2 +https://github.com/jennywassweet/ochi"


RETRIES = 3  # on 429 (rate limit: 60 requests/min with a token, 25 without)


def _token() -> str | None:
    return os.environ.get("DISCOGS_TOKEN") or os.environ.get("DISCOGS_PERSONAL_ACCESS_TOKEN")


def _get(path: str, **params) -> dict:
    params = {k: v for k, v in params.items() if v not in (None, "")}
    url = f"{API}{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
    headers = {"User-Agent": UA}
    if token := _token():
        headers["Authorization"] = f"Discogs token={token}"
    for attempt in range(RETRIES + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < RETRIES:
                time.sleep(_retry_after(e, attempt))
                continue
            raise RuntimeError(_explain(e, path)) from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"Can't reach the Discogs API: {e.reason}") from None
    raise AssertionError("unreachable")


def _retry_after(e: urllib.error.HTTPError, attempt: int) -> float:
    try:
        return min(float(e.headers.get("Retry-After", "")), 60.0)
    except ValueError:
        return 2.0 * 2 ** attempt  # 2, 4, 8 s


def _explain(e: urllib.error.HTTPError, path: str) -> str:
    try:
        message = json.load(e).get("message", "")
    except Exception:  # noqa: BLE001
        message = ""
    if e.code == 401:
        hint = ("DISCOGS_TOKEN looks wrong" if _token() else
                "this needs a token: put DISCOGS_TOKEN into .env (see README)")
        return f"Discogs API {path}: not authorized, {hint}."
    if e.code == 404:
        return f"Discogs API {path}: not found (wrong id, or a listing that was sold or removed)."
    if e.code == 429:
        return f"Discogs API {path}: rate limit still hit after {RETRIES} retries; wait a minute."
    return f"Discogs API {path}: HTTP {e.code} {message or e.reason}".rstrip()


def search(q: str, type: str = "release", format: str = "", per_page: int = 15) -> list[dict]:
    d = _get("/database/search", q=q, type=type, format=format, per_page=per_page)
    out = []
    for r in d.get("results", []):
        out.append({k: r.get(k) for k in ("id", "type", "title", "year", "country", "catno", "master_id")
                    if r.get(k)} | {"format": ", ".join(r.get("format", [])),
                                    "label": ", ".join(dict.fromkeys(r.get("label", [])))[:80],
                                    "style": ", ".join(r.get("style", []))})
    return out


def release(release_id: int) -> dict:
    r = _get(f"/releases/{release_id}", curr_abbr="EUR")
    return {
        "id": r["id"],
        "title": f"{', '.join(a['name'] for a in r.get('artists', []))} – {r.get('title')}",
        "year": r.get("year"),
        "country": r.get("country"),
        "labels": [f"{lb['name']} {lb.get('catno', '')}".strip() for lb in r.get("labels", [])],
        "formats": [f"{f.get('qty', '')}×{f['name']} {', '.join(f.get('descriptions', []))} {f.get('text', '')}".strip()
                    for f in r.get("formats", [])],
        "genres": r.get("genres", []),
        "styles": r.get("styles", []),
        "master_id": r.get("master_id"),
        "for_sale": r.get("num_for_sale"),
        "lowest_price_eur": r.get("lowest_price"),
        "have_want": f"{r.get('community', {}).get('have')}/{r.get('community', {}).get('want')}",
        "tracklist": [f"{t.get('position', '')} {t.get('title', '')} {t.get('duration', '')}".strip()
                      for t in r.get("tracklist", [])],
        "url": r.get("uri"),
    }


def master_versions(master_id: int, format: str = "Vinyl") -> list[dict]:
    d = _get(f"/masters/{master_id}/versions", format=format, per_page=100)
    out = []
    for v in d.get("versions", []):
        c = v.get("stats", {}).get("community", {})
        out.append({"id": v["id"], "label": v.get("label"), "catno": v.get("catno"), "country": v.get("country"),
                    "released": v.get("released"), "format": v.get("format"),
                    "have_want": f"{c.get('in_collection')}/{c.get('in_wantlist')}"})
    return out


def listing(listing_id: int) -> dict:
    d = _get(f"/marketplace/listings/{listing_id}", curr_abbr="EUR")
    s = d.get("seller", {})
    return {
        "id": d["id"], "status": d.get("status"),
        "release": d.get("release", {}).get("description"),
        "media": d.get("condition"), "sleeve": d.get("sleeve_condition"),
        "price": d.get("price", {}).get("value"), "shipping": d.get("shipping_price", {}).get("value"),
        "currency": d.get("price", {}).get("currency"),
        "ships_from": d.get("ships_from"), "comments": d.get("comments"),
        "seller": s.get("username"), "rating": s.get("stats", {}).get("rating"),
        "ratings_total": s.get("stats", {}).get("total"), "url": d.get("uri"),
    }


def seller_id(username: str) -> int:
    return _get(f"/users/{urllib.parse.quote(username)}")["id"]


def shipping(seller: str, country: str) -> dict:
    """A seller's shipping terms to one country, as Discogs shows them under a listing's "shipping" button.

    Uses the site's own v3 endpoint (undocumented, needs a token). Read-only: a GET with the token, no session,
    so it never touches a cart. Rates are Discogs' own descriptions ("2 and up items: €2.00 per each additional
    1 item"); combining them into an order total is left to the caller.
    """
    d = _get("/v3/marketplace/shipping/policies", seller_id=seller_id(seller), country=country)
    out: dict = {"seller": seller, "country": country, "currency": d.get("currency")}
    policies = d.get("policies") or []
    if not policies:
        out["ships"] = False
        out["note"] = f"the seller has no shipping policy for {country}: doesn't ship there"
        return out
    out["ships"] = True
    methods = []
    for p in policies:
        if p.get("free_shipping"):
            out["free_shipping_from"] = p.get("formatted_free_shipping_min_order_val") or "any order"
        for m in p.get("methods", []):
            row = {"name": m.get("name")}
            if m.get("delivery_max"):
                row["days"] = f"{m.get('delivery_min')}-{m['delivery_max']}"
            if m.get("range_type"):
                row["by"] = m["range_type"]  # quantity (items) or weight (grams)
            if (m.get("constraint_price") or 0) > 0:
                row["min_order"] = m.get("formatted_constraint_price")
            if rates := [r["description"] for r in m.get("ranges", []) if r.get("description")]:
                row["rates"] = rates
            methods.append(row)
    out["methods"] = methods
    return out


MAX_PAGES = 20  # 100 items each: wantlists and collections up to 2000 items


def _me() -> str:
    """Username of the DISCOGS_TOKEN owner."""
    return _get("/oauth/identity")["username"]


def _all_pages(path: str, key: str) -> list[dict]:
    out: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        d = _get(path, per_page=100, page=page)
        out += d.get(key, [])
        if page >= d.get("pagination", {}).get("pages", 1):
            break
    return out


def _release_row(info: dict) -> dict:
    """The compact form of a release's basic_information (wantlist and collection entries)."""
    formats = "; ".join(f"{f.get('qty', '1')}×{f.get('name', '')} {', '.join(f.get('descriptions', []))}".strip()
                        for f in info.get("formats", []))
    labels = ", ".join(dict.fromkeys(f"{lb.get('name', '')} {lb.get('catno', '')}".strip()
                                     for lb in info.get("labels", [])))
    row = {
        "release_id": info.get("id"),
        "title": f"{', '.join(a.get('name', '') for a in info.get('artists', []))} – {info.get('title')}",
        "year": info.get("year"),
        "format": formats,
        "label": labels,
        "styles": ", ".join(info.get("styles") or info.get("genres") or []),
        "master_id": info.get("master_id"),
    }
    return {k: v for k, v in row.items() if v}


def _listed(entries: list[dict], query: str, limit: int, extra) -> list[dict]:
    rows = [_release_row(e.get("basic_information", {})) | extra(e) for e in entries]
    if q := query.strip().lower():
        rows = [r for r in rows if q in " ".join(str(v) for v in r.values()).lower()]
    return rows[:limit]


def wantlist(username: str = "", query: str = "", limit: int = 500) -> list[dict]:
    user = username or _me()
    entries = _all_pages(f"/users/{urllib.parse.quote(user)}/wants", "wants")
    return _listed(entries, query, limit, lambda e: {k: v for k, v in {
        "added": (e.get("date_added") or "")[:10], "notes": e.get("notes")}.items() if v})


def collection(username: str = "", query: str = "", limit: int = 500) -> list[dict]:
    user = username or _me()
    entries = _all_pages(f"/users/{urllib.parse.quote(user)}/collection/folders/0/releases", "releases")
    return _listed(entries, query, limit, lambda e: {k: v for k, v in {
        "added": (e.get("date_added") or "")[:10], "rating": e.get("rating")}.items() if v})
