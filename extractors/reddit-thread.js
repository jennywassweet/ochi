// ==Extractor==
// @name        reddit-thread
// @match       https://www.reddit.com/r/*/comments/*
// @match       https://old.reddit.com/r/*/comments/*
// @description Reddit thread: post + comment tree via Reddit's own .json view
// ==/Extractor==

async function extract() {
  const path = location.pathname.replace(/\/$/, '');
  const data = await (await fetch(`${path}.json?limit=500&raw_json=1`, { credentials: 'include' })).json();
  const post = data[0].data.children[0].data;
  const out = [
    `# ${post.title}`,
    `r/${post.subreddit} · u/${post.author} · ${post.score} pts · ${post.num_comments} comments`,
    post.url !== `https://www.reddit.com${post.permalink}` ? `link: ${post.url}` : null,
    post.selftext || null,
    '',
    '## Comments',
  ];
  const walk = (children, depth) => {
    for (const c of children || []) {
      if (c.kind !== 't1') continue;
      const d = c.data;
      const body = (d.body || '').replace(/\n+/g, ' ').slice(0, 1500);
      out.push(`${'  '.repeat(depth)}- [${d.score}] u/${d.author}: ${body}`);
      if (d.replies && d.replies.data) walk(d.replies.data.children, depth + 1);
    }
  };
  walk(data[1].data.children, 0);
  return out.filter(l => l !== null).join('\n');
}
