# Test fixtures

Saved pages for extractor tests. Strip scripts, styles and anything tied to the account that took the
snapshot (user id, username, cart, wantlist) before committing.

- `discogs-shop-list.html`: `https://www.discogs.com/shop/list?genre=Rock&formatName=Vinyl`, 2026-10-18
  (`ochi-try --snapshot`, then cleaned). The new marketplace is a React app: the HTML has the filters, the
  results footer ("1 – 25 of 13.3M") and only the first few `.msr-listing-card` rows.
- `discogs-shop-list.graphql.json`: the `MarketplaceSearch` GraphQL response the same page loaded
  (25 listings, prices in EUR as seen by the buyer), with the `viewer` block and per-user flags removed.
  `extractors/discogs-market.js` reads listings from this response, not from the HTML.
- `discogs-seller.html`: synthetic, the old marketplace table (seller shop) reduced to the classes the
  extractor reads, with prices in mixed formats (`€12.50`, `8,99 €`, `€1,234.50`, `€3.00`) and one Generic sleeve.
- `reddit-thread.json`, `reddit-sub.json`: synthetic, minimal shapes of Reddit's `.json` views.
- `discogs-release-sellers.html`: `https://www.discogs.com/sell/release/13844130`, 2026-10-18; only the listings
  table kept, scripts and images removed, seller names replaced by `seller1…`. Sellers in EUR and USD, two
  without shipping to the buyer, one with a free-shipping threshold.
