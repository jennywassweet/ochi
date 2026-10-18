# Test fixtures

Saved pages for extractor tests. Strip scripts, styles and anything tied to the account that took the
snapshot (user id, username, cart, wantlist) before committing.

- `discogs-shop-list.html`: `https://www.discogs.com/shop/list?genre=Rock&formatName=Vinyl`, 2026-10-18
  (`ochi-try --snapshot`, then cleaned). The new marketplace is a React app: the HTML has the filters, the
  results footer ("1 – 25 of 13.3M") and only the first few `.msr-listing-card` rows.
- `discogs-shop-list.graphql.json`: the `MarketplaceSearch` GraphQL response the same page loaded
  (25 listings, prices in EUR as seen by the buyer), with the `viewer` block and per-user flags removed.
  `extractors/discogs-market.js` reads listings from this response, not from the HTML.
