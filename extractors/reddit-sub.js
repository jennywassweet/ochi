// ==Extractor==
// @name        reddit-sub
// @match       https://www.reddit.com/r/*
// @match       https://old.reddit.com/r/*
// @description Subreddit feed (hot/new/top as in the URL): posts with score, comments, link — via Reddit's .json view
// ==/Extractor==

async function extract() {
  // thread pages are handled by reddit-thread; here: listing
  const path = location.pathname.replace(/\/$/, '');
  const data = await (await fetch(`${path}.json?limit=40&raw_json=1${location.search.replace('?', '&')}`,
                                  { credentials: 'include' })).json();
  const posts = (data.data?.children || []).filter(c => c.kind === 't3').map(c => c.data);
  const lines = [`# r/${posts[0]?.subreddit || path.split('/')[2]} — ${location.href}`];
  for (const p of posts) {
    const age = Math.round((Date.now() / 1000 - p.created_utc) / 3600);
    const flair = p.link_flair_text ? `[${p.link_flair_text}] ` : '';
    const pin = p.stickied ? '📌 ' : '';
    const self = p.is_self && p.selftext ? ` — ${p.selftext.replace(/\s+/g, ' ').slice(0, 220)}` : '';
    const ext = !p.is_self ? ` (${p.domain})` : '';
    lines.push(`- ${pin}${flair}${p.title}${ext} · ${p.score}↑ ${p.num_comments}💬 ${age}h · https://reddit.com${p.permalink}${self}`);
  }
  return lines.join('\n');
}
