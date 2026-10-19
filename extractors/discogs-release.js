// ==Extractor==
// @name        discogs-release
// @match       https://www.discogs.com/release/*
// @match       https://www.discogs.com/??/release/*
// @match       https://www.discogs.com/??_??/release/*
// @wait        #release-stats li
// @description Discogs release page: have/want, rating and the sales history summary (last sold, low / median / high price paid). Copies for sale now, lowest price and release details come from discogs_release.
// ==/Extractor==

async function extract() {
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const id = +(location.pathname.match(/release\/(\d+)/) || [])[1] || null;

  // "Statistics" box: <li><span>Name:</span> value</li>; class names are build hashes, so only structure is used
  const stats = {};
  for (const li of document.querySelectorAll('#release-stats li')) {
    const [label, ...values] = li.children;
    const key = clean(label?.textContent).replace(/:$/, '').toLowerCase().replace(/\s+/g, '_');
    if (!key) continue;
    const time = li.querySelector('time[datetime]');
    const value = time ? time.getAttribute('datetime') : clean(values.map(e => e.textContent).join(' '));
    stats[key] = /^\d[\d,]*$/.test(value) ? +value.replace(/,/g, '') : value;
  }

  // (the "for sale" box is a lazily loaded widget; the same numbers come from the API via discogs_release)
  return {
    id,
    title: clean(document.querySelector('h1')?.textContent),
    url: location.origin + location.pathname,
    stats,
    sellers_url: id ? `https://www.discogs.com/sell/release/${id}` : null,
    sales_history_url: id ? `https://www.discogs.com/sell/history/${id}` : null,
  };
}
