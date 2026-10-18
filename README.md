# ochi · очі

Eyes on the web for your AI assistant. A tiny MCP server that reads pages **through your own Chrome**
(so Cloudflare & co. see a normal person) and turns them into clean data with
small per-site **extractor** scripts — Greasemonkey-style `.js` files in `extractors/`.

```
Claude ──MCP/stdio──▶ ochi (Python) ──Playwright/CDP──▶ your Chrome ──HTTPS──▶ site
```

No Docker, no global Node. Python is managed by `uv` inside the project.

## Setup (once)

1. **uv** — see [installation](https://docs.astral.sh/uv/getting-started/installation/).
2. **Get the code** — `git clone https://github.com/jennywassweet/ochi && cd ochi`
3. **Browser** — ochi starts its own Chrome window (separate profile `~/.ochi-profile`,
   debugging port 9222) the first time a tool needs it. It looks for Chrome, Chromium,
   Brave or Edge in the usual places; to change path/profile/port/autostart,
   `cp ochi.example.toml ochi.toml` and edit it. Log in there only to sites ochi needs
   (Discogs, Reddit…). No mail, no banking.
4. **Discogs token** (optional, for the `discogs_*` API tools): `cp .env.example .env` and fill `DISCOGS_TOKEN`.
5. **Try it** without MCP (put any Discogs seller name instead of `SELLER`):
   ```sh
   uv run ochi-try "https://www.discogs.com/seller/SELLER/profile?format=Vinyl&ochi_max=20"
   uv run ochi-try --snapshot "https://www.discogs.com/seller/SELLER/profile"
   ```
6. **Hook into Claude Desktop** — add to `claude_desktop_config.json`
   (macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`):
   ```json
   "ochi": {
     "command": "uv",
     "args": ["--directory", "/absolute/path/to/ochi", "run", "ochi"]
   }
   ```
   (inside `"mcpServers": { … }`, then restart Claude Desktop; if `uv` isn't found,
   use its absolute path from `which uv` / `where uv`)

## Tools

| tool | what |
|---|---|
| `fetch(url)` | open url in a new tab, run matching extractor, close the tab, return compact text/JSON lines |
| `look(tab?)` | read a tab that is already open (default: the visible one) without navigating |
| `tabs()` | list open tabs in the ochi browser |
| `show(url)` | open a page in a new tab and leave it open for you to see |
| `list_extractors()` | known sites and URL patterns |
| `snapshot(url)` | save rendered HTML to `snapshots/` — for writing/fixing extractors |
| `browser_start()` / `browser_status()` | start / check the ochi Chrome |
| `discogs_search`, `discogs_release`, `discogs_master_versions`, `discogs_listing` | the bits of the Discogs API we use (structured, no browser) |

## Configuration

`ochi.toml` (optional, see `ochi.example.toml`) — `[chrome]` path, profile, port, autostart, args.
Environment variables override it: `OCHI_CONFIG` (path to the toml), `OCHI_CHROME`,
`OCHI_PROFILE`, `OCHI_PORT`, `OCHI_EXTRACTORS` (extractors folder). Secrets go to `.env`.

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
`@match` is a glob where `*` matches anything (including `/`); the longest matching
pattern wins, and an extractor matching `*` is the fallback.

## Extractor-specific URL params

- `discogs-market`: `ochi_max=20` keeps items up to that price; `ochi_pages=10` caps pagination (250 per page).

## Security

ochi gives the model a real, logged-in browser. Keep that in mind:

- Use the separate ochi profile and log in only where you need to.
- `fetch`/`show` open whatever URL the model asks for, and `look` reads the visible tab.
- Page content is untrusted text and can contain instructions aimed at the model (prompt injection).
- While the browser runs, its debugging port (9222 on 127.0.0.1) lets any local program control it.

## Etiquette

Personal use, a handful of pages per session, pauses between pages. No paywall bypassing,
no captcha solving — if a site asks for a human, the human clicks.

## License

MIT
