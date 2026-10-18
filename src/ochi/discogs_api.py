"""The few Discogs API calls we actually use, compact outputs. Token: DISCOGS_TOKEN in .env."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

API = "https://api.discogs.com"
UA = "ochi/0.1 +https://github.com/jennywassweet/ochi"


def _get(path: str, **params) -> dict:
    params = {k: v for k, v in params.items() if v not in (None, "")}
    url = f"{API}{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
    headers = {"User-Agent": UA}
    if token := os.environ.get("DISCOGS_TOKEN") or os.environ.get("DISCOGS_PERSONAL_ACCESS_TOKEN"):
        headers["Authorization"] = f"Discogs token={token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
        return json.load(r)


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
        "labels": [f"{l['name']} {l.get('catno', '')}".strip() for l in r.get("labels", [])],
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
    return [{"id": v["id"], "label": v.get("label"), "catno": v.get("catno"), "country": v.get("country"),
             "released": v.get("released"), "format": v.get("format"),
             "have_want": f"{v['stats']['community']['in_collection']}/{v['stats']['community']['in_wantlist']}"}
            for v in d.get("versions", [])]


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
