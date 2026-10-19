# ochi — notes for coding agents

- Python ≥3.11, managed with `uv`. Run: `uv run ochi` (MCP stdio), `uv run ochi-try <url>` (manual).
- `mcp` is pinned `<2` (we use `mcp.server.fastmcp.FastMCP`).
- ochi uses its own Chromium-based browser with a separate profile, reached over CDP on `127.0.0.1:<port>`.
  If nothing answers on the port and `autostart` is on, `chrome.ensure()` launches it (path auto-detected
  by `config.find_chrome()` unless set). ochi never closes the browser, only the tabs it opened for `fetch`/`snapshot`.
- Files live in `config.home()`: `OCHI_HOME`, else the repo root when run from a checkout, else the per-user
  config dir (installed via `uvx`/pip; `ochi init` fills it). There: optional `ochi.toml` (template
  `ochi.example.toml`, not committed), `.env` secrets, `extractors/` (user's, layered over built-ins), `snapshots/`.
  Env overrides: `OCHI_CONFIG`, `OCHI_CHROME`, `OCHI_PROFILE`, `OCHI_PORT`, `OCHI_EXTRACTORS`.
- Built-in extractors and examples are found via `config.bundled()`: repo root in a checkout, `ochi/data/` in the
  wheel (`force-include` in pyproject.toml; `tests/test_package.py` builds and runs the wheel).
- Extractors live in `extractors/*.js` with a `// ==Extractor==` header (`@name`, `@match` glob, `@wait`, `@description`)
  and define `async function extract()`; `extractors.find()` prefers the longest specific match over the generic `*`.
- Discogs/Reddit DOM selectors are best-effort; when they break, take a `snapshot`, keep the HTML as a test fixture,
  fix the selector, add a test.
- Tool docstrings are read by any user's model: keep them neutral (no personal names).
- `urlguard.check()` gates every URL that fetch/show/snapshot/ochi-try open (http(s) only, no private hosts
  unless `[urls]` allows). `browser.connect()` keeps one Playwright driver + CDP connection per event loop;
  never `async with async_playwright()` per call. Discogs API errors become readable `RuntimeError`s, 429 retried.
- ochi is the tool layer only: tools fetch, filter and return compact data. No taste profiles, recommendations,
  workflow prompts or personal data in ochi; judging and personalizing is the model's job (it has its own memory).
  Prefer the site's own filters and big pages over the API; use the API to enrich short lists.
- Extractor-side `ochi_*` URL params (see README) shape results inside the page and are stripped before requests.
- Do not add captcha solving, stealth evasion, or paywall bypass.
- Tests: `uv run pytest` (no network; `browser`-marked ones run extractors in headless Chromium against
  `tests/fixtures/`), lint: `uv run ruff check .`. CI: `.github/workflows/ci.yml`, Linux/macOS/Windows.
- Next ideas: `discogs_wantlist`, Readability.js for `generic`, Last.fm as a data source, caching, more sites.
  PyPI was considered and skipped for now (no commitment to a release cadence); install is `uvx --from git+…`.
