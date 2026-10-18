# ochi · очі

Eyes on the web. A tiny MCP server that reads pages **through your own Chrome**
(so Cloudflare & co. see a normal person) and turns them into clean data with
small per-site **extractor** scripts — Greasemonkey-style `.js` files in `extractors/`.

```
Claude ──MCP/stdio──▶ ochi (Python) ──Playwright/CDP──▶ your Chrome ──HTTPS──▶ site
```

No Docker, no global Node. Python is managed by `uv` inside the project.

## Setup (once)

1. **uv** — `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. **Chrome with a separate profile and debugging port** (keep this window open, minimize it):
   ```sh
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
     --remote-debugging-port=9222 --user-data-dir=$HOME/.ochi-profile
   ```
   Log in there only to sites ochi needs (Discogs, Reddit…). No mail, no banking.
3. **Try it** without MCP:
   ```sh
   cd ~/dev-projects/ochi
   uv run ochi-try "https://www.discogs.com/seller/SELLER/profile?style=Psychedelic+Rock&format=Vinyl&ochi_max=20"
   uv run ochi-try --snapshot "https://www.discogs.com/seller/SELLER/profile"
   ```
4. **Hook into Claude Desktop** — `~/Library/Application Support/Claude/claude_desktop_config.json`:
   ```json
   "ochi": {
     "command": "uv",
     "args": ["--directory", "/absolute/path/to/ochi", "run", "ochi"]
   }
   ```
   (inside `"mcpServers": { … }`, then restart Claude Desktop)

## Tools

| tool | what |
|---|---|
| `fetch(url)` | open url in Chrome, run matching extractor, return compact text/JSON lines |
| `list_extractors()` | known sites and URL patterns |
| `snapshot(url)` | save rendered HTML to `snapshots/` — for writing/fixing extractors |

## Writing an extractor

```js
// ==Extractor==
// @name        my-site
// @match       https://example.com/articles/*
// @wait        article            (optional CSS selector to wait for)
// @description one line for list_extractors
// ==/Extractor==

async function extract() {
  // runs INSIDE the page: document, fetch() with the page's cookies, etc.
  return { items: [...] };   // or a string
}
```

A result `{..., items: [...]}` is rendered one item per line (cheap for the model).

## Extractor-specific URL params

- `discogs-market`: `ochi_max=20` keeps items up to that price; `ochi_pages=10` caps pagination (250 per page).

## Etiquette

Personal use, a handful of pages per session, pauses between pages. No paywall bypassing,
no captcha solving — if a site asks for a human, the human clicks.
