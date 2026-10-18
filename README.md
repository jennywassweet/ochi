# ochi · очі

Eyes on the web for your AI assistant. A tiny MCP server that reads pages **through your own Chrome**
(so Cloudflare & co. see a normal person) and turns them into clean data with
small per-site **extractor** scripts: Greasemonkey-style `.js` files.

```
Claude ──MCP/stdio──▶ ochi (Python) ──Playwright/CDP──▶ your Chrome ──HTTPS──▶ site
```

No Docker, no global Node: Python and dependencies are handled by `uv`. Works on macOS, Windows and Linux.

## Setup (once)

1. **uv**: see [installation](https://docs.astral.sh/uv/getting-started/installation/).
2. **Config folder**:
   ```sh
   uvx --from git+https://github.com/jennywassweet/ochi ochi init
   ```
   This creates `ochi.toml`, `.env` and an `extractors/` folder for your own extractors in
   `~/Library/Application Support/ochi` (macOS), `%APPDATA%\ochi` (Windows) or `~/.config/ochi` (Linux),
   and shows which browser it found.
3. **Browser**: ochi starts its own Chrome window (separate profile `~/.ochi-profile`,
   debugging port 9222) the first time a tool needs it. It finds Chrome, Chromium, Brave or Edge
   in the usual places; path, profile, port and autostart can be changed in `ochi.toml`.
   Log in there only to sites ochi needs (Discogs, Reddit…). No mail, no banking.
4. **Discogs token** (optional, for the `discogs_*` API tools): put it into `.env` as `DISCOGS_TOKEN`
   ([get one here](https://www.discogs.com/settings/developers)).
5. **Hook into Claude Desktop**: add to `claude_desktop_config.json`
   (macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`):
   ```json
   "ochi": {
     "command": "uvx",
     "args": ["--from", "git+https://github.com/jennywassweet/ochi", "ochi"]
   }
   ```
   (inside `"mcpServers": { … }`, then restart Claude Desktop; if `uvx` isn't found,
   use its absolute path from `which uvx` / `where uvx`). Other MCP clients take the same command.
6. **Try it** without MCP (put any Discogs seller name instead of `SELLER`):
   ```sh
   uvx --from git+https://github.com/jennywassweet/ochi ochi-try "https://www.discogs.com/seller/SELLER/profile?format=Vinyl&ochi_max=20"
   ```

**From a clone** (to hack on ochi): `git clone https://github.com/jennywassweet/ochi && cd ochi`, then
`uv run ochi-try <url>`, and in the Claude config use `"command": "uv"`,
`"args": ["--directory", "/absolute/path/to/ochi", "run", "ochi"]`. Run from a clone, ochi keeps
`ochi.toml`, `.env`, `snapshots/` and reads `extractors/` right in the repo folder.

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

ochi's home folder (see Setup; `OCHI_HOME` moves it) holds:

- `ochi.toml` (optional, see `ochi.example.toml`): `[chrome]` path, profile, port, autostart, args;
- `.env`: secrets (`DISCOGS_TOKEN`);
- `extractors/`: your own extractors, loaded next to the built-in ones (same `@name` replaces a built-in one);
- `snapshots/`: output of `snapshot`.

Environment variables override the file: `OCHI_CONFIG` (path to the toml), `OCHI_CHROME`,
`OCHI_PROFILE`, `OCHI_PORT`, `OCHI_EXTRACTORS` (your extractors folder).

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

## Development

```sh
uv sync                                  # dev tools included
uv run ruff check .
uv run playwright install chromium       # once; browser tests otherwise use an installed Chrome
uv run pytest
```

Tests never touch the network: extractors run in headless Chromium against saved pages and JSON in
`tests/fixtures/`. When a site changes its layout, save a new snapshot there (strip anything tied to your
account), fix the extractor, adjust the test. CI runs the suite on Linux, macOS and Windows.

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
