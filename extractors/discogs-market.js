// ==Extractor==
// @name        discogs-market
// @match       https://www.discogs.com/seller/*
// @match       https://www.discogs.com/sell/*
// @match       https://www.discogs.com/*/seller/*
// @match       https://www.discogs.com/*/sell/*
// @match       https://www.discogs.com/shop/*
// @match       https://www.discogs.com/*/shop/*
// @wait        table.mpitems, .pagination_total, .msr-listing-card, .msr-results-footer
// @description Discogs marketplace lists (marketplace search /shop/list, seller shop with filters, sellers of a release). Extra URL param ochi_max=20 keeps only items up to that price.
// ==/Extractor==

async function extract() {
  const here = new URL(location.href);
  const maxPrice = parseFloat(here.searchParams.get('ochi_max') || 'Infinity');
  const maxPages = parseInt(here.searchParams.get('ochi_pages') || '10', 10);
  here.searchParams.delete('ochi_max');
  here.searchParams.delete('ochi_pages');

  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  // "€1,234.50", "1.234,50 €", "$12.5", "12,50" -> number: the last , or . followed by 1-2 digits is the decimal point
  const num = s => {
    let t = (clean(s).match(/\d[\d.,]*/) || [])[0];
    if (!t) return null;
    const dec = Math.max(t.lastIndexOf('.'), t.lastIndexOf(','));
    t = dec > -1 && t.length - dec - 1 <= 2
      ? t.slice(0, dec).replace(/[.,]/g, '') + '.' + t.slice(dec + 1)
      : t.replace(/[.,]/g, '');
    return parseFloat(t);
  };

  const parseRows = doc => [...doc.querySelectorAll('table.mpitems tbody tr, tr.shortcut_navigable')].map(tr => {
    const q = s => tr.querySelector(s);
    const link = q('a.item_description_title') || q('a[href*="/sell/item/"]');
    if (!link) return null;
    const cond = clean(q('.item_condition')?.innerText);
    const sellerLis = [...tr.querySelectorAll('.seller_info li')].map(li => clean(li.innerText));
    const row = {
      id: (link.href.match(/item\/(\d+)/) || [])[1],
      title: clean(link.innerText),
      label: clean(q('.label_and_cat, .item_label')?.innerText).slice(0, 80),
      media: clean((cond.match(/Media:\s*(.*?)\s*(?:Sleeve:|$)/) || [])[1]).slice(0, 40),
      sleeve: clean((cond.match(/Sleeve:\s*(.*)$/) || [])[1]).slice(0, 40),
      price: clean(q('.price')?.innerText),
      shipping: clean(q('.item_shipping')?.innerText).replace(/\s*shipping.*$/i, ''),
      seller: clean(q('.seller_info a[href*="/seller/"], .seller_info strong a')?.innerText),
      rating: (sellerLis.join(' ').match(/(\d{2,3}(?:\.\d)?%)/) || [])[1] || '',
      from: (sellerLis.join(' ').match(/Ships From:\s*([^,]+?)(?:$|\s{2}|Buy)/i) || [])[1] || '',
    };
    if (!row.media && cond) row.cond = cond.slice(0, 80);
    row._p = num(row.price);
    return row;
  }).filter(Boolean);

  // New marketplace (/shop/list, 2026): a React app that renders only part of each page and loads
  // listings from the site's own GraphQL endpoint. Reuse the exact request the page made (its filters,
  // sort and persisted-query hash come from the site), changing only page size and cursor.
  const SHOP_PAGE_SIZE = 250; // the site allows 25/50/100/250
  const GRADES = {
    MINT: 'Mint (M)', NEAR_MINT: 'Near Mint (NM or M-)', VERY_GOOD_PLUS: 'Very Good Plus (VG+)',
    VERY_GOOD: 'Very Good (VG)', GOOD_PLUS: 'Good Plus (G+)', GOOD: 'Good (G)', FAIR: 'Fair (F)', POOR: 'Poor (P)',
    GENERIC: 'Generic', NOT_GRADED: 'Not Graded', NO_COVER: 'No Cover',
  };
  const grade = g => GRADES[g] || (g ? g.toLowerCase().replace(/_/g, ' ').replace(/^./, c => c.toUpperCase()) : '');
  const money = p => {
    if (!p || p.amount == null) return '';
    try { return new Intl.NumberFormat('en-US', { style: 'currency', currency: p.currency }).format(p.amount); }
    catch { return `${p.amount} ${p.currency}`; }
  };
  const shopRow = n => {
    const r = n.release || {};
    const artists = (r.primaryArtists || []).map(a => a.displayName).join(', ');
    const fmt = r.formatSummary?.description;
    const label = (r.labels || []).find(l => l.labelRole === 'LABEL') || (r.labels || [])[0];
    const price = n.buyerPrice || n.price;
    const ship = n.shipping?.buyerPrice || n.shipping?.price;
    const rating = n.sellerInfo?.ratingCount ? n.sellerInfo.rating : null;
    return {
      id: String(n.id),
      title: clean(`${artists ? artists + ' - ' : ''}${r.title || ''}${fmt ? ` (${fmt})` : ''}`),
      label: label ? clean(`${label.displayName}${label.catalogNumber ? ' · ' + label.catalogNumber : ''}`).slice(0, 80) : '',
      media: grade(n.mediaCondition),
      sleeve: grade(n.sleeveCondition),
      price: money(price),
      shipping: ship && ship.amount > 0 ? money(ship) : '',
      seller: n.seller?.username || '',
      rating: rating == null ? '' : `${+rating.toFixed(1)}%`,
      from: n.sellerInfo?.shipsFrom || '',
      release: r.discogsId,
      _p: price?.amount ?? null,
    };
  };
  const findShopQuery = async () => {
    // the page fires the query after hydration; give it up to ~15 s
    for (let i = 0; i < 60; i++) {
      const hits = performance.getEntriesByType('resource').map(e => e.name)
        .filter(u => u.includes('/graphql') && u.includes('operationName=MarketplaceSearch'));
      if (hits.length) return new URL(hits[hits.length - 1]);
      await new Promise(r => setTimeout(r, 250));
    }
    return null;
  };

  const items = new Map();
  let total = null;
  if (/^\/(?:[a-z]{2}\/)?shop\//.test(location.pathname)) {
    const q = await findShopQuery();
    if (!q) return { error: 'marketplace query not found on page (layout changed?)', url: location.href };
    const vars = JSON.parse(q.searchParams.get('variables') || '{}');
    vars.first = SHOP_PAGE_SIZE;
    delete vars.after;
    for (let page = 1; page <= maxPages; page++) {
      q.searchParams.set('variables', JSON.stringify(vars));
      const res = await fetch(q.href, {
        credentials: 'include',
        headers: { accept: 'application/graphql-response+json,application/json;q=0.9', 'content-type': 'application/json' },
      });
      const body = await res.json().catch(() => null);
      const ms = body?.data?.marketplaceSearch;
      if (!ms) {
        if (page === 1) return { error: `marketplace query failed (HTTP ${res.status})`, details: body?.errors?.map(e => e.message), url: location.href };
        break;
      }
      if (total === null) total = ms.totalCount ?? null;
      const before = items.size;
      (ms.edges || []).forEach(e => e.node && items.set(String(e.node.id), shopRow(e.node)));
      if (items.size === before || !ms.pageInfo?.hasNextPage || !ms.pageInfo.endCursor) break;
      vars.after = ms.pageInfo.endCursor;
      if (page < maxPages) await new Promise(r => setTimeout(r, 1200));
    }
  } else {
    here.searchParams.set('limit', '250');
    for (let page = 1; page <= maxPages; page++) {
      here.searchParams.set('page', page);
      let doc = document;
      if (page > 1 || location.href !== here.href) {
        const html = await (await fetch(here.href, { credentials: 'include' })).text();
        doc = new DOMParser().parseFromString(html, 'text/html');
      }
      if (total === null) {
        const t = clean(doc.querySelector('.pagination_total')?.innerText);
        total = (t.match(/of\s+([\d,.]+)/) || [])[1] || t || null;
      }
      const before = items.size;
      parseRows(doc).forEach(r => items.set(r.id, r));
      if (items.size === before) break;
      if (page < maxPages) await new Promise(r => setTimeout(r, 1200));
    }
  }

  const all = [...items.values()];
  const kept = all.filter(r => r._p === null || r._p <= maxPrice);
  // tidy: short grades, no "Label:" noise
  kept.forEach(r => {
    delete r._p;
    if (r.media) r.media = r.media.replace(/\).*$/, ')');
    const w = (r.from || '').match(/\s*Has (\d+) items? I want/i);
    if (w) { r.from = r.from.replace(w[0], '').trim(); if (+w[1] > 0) r.wants = +w[1]; }
    if (r.shipping === '+') r.shipping = '';
    if (r.label) r.label = r.label.replace(/^Label:\s*/, '').replace(/\s*Cat#:\s*/, ' · ');
  });
  // fields identical across all rows (seller shop: seller, rating, from, often shipping) go to the header
  const common = {};
  if (kept.length > 1) {
    for (const k of ['seller', 'rating', 'from', 'shipping', 'media', 'sleeve']) {
      const v = kept[0][k];
      if (v && kept.every(r => r[k] === v)) { common[k] = v; kept.forEach(r => delete r[k]); }
    }
  }
  kept.forEach(r => Object.keys(r).forEach(k => r[k] === '' && delete r[k]));
  return {
    common,
    url: here.href.replace(/&page=\d+/, ''),
    total_on_site: total,
    fetched: all.length,
    shown: kept.length,
    max_price: isFinite(maxPrice) ? maxPrice : null,
    items: kept,
  };
}
