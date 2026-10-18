// ==Extractor==
// @name        discogs-market
// @match       https://www.discogs.com/seller/*
// @match       https://www.discogs.com/sell/*
// @match       https://www.discogs.com/*/seller/*
// @match       https://www.discogs.com/*/sell/*
// @wait        table.mpitems, .pagination_total
// @description Discogs marketplace lists (seller shop with filters, sellers of a release). Extra URL param ochi_max=20 keeps only items up to that price.
// ==/Extractor==

async function extract() {
  const here = new URL(location.href);
  const maxPrice = parseFloat(here.searchParams.get('ochi_max') || 'Infinity');
  const maxPages = parseInt(here.searchParams.get('ochi_pages') || '10', 10);
  here.searchParams.delete('ochi_max');
  here.searchParams.delete('ochi_pages');
  here.searchParams.set('limit', '250');

  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const num = s => { const m = clean(s).replace(',', '.').match(/(\d+(?:\.\d+)?)/); return m ? parseFloat(m[1]) : null; };

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

  const items = new Map();
  let total = null;
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
