# ochi — notes for coding agents

- Python ≥3.11, managed with `uv`. Run: `uv run ochi` (MCP stdio), `uv run ochi-try <url>` (manual).
- `mcp` is pinned `<2` (we use `mcp.server.fastmcp.FastMCP`).
- ochi uses its own Chromium-based browser with a separate profile, reached over CDP on `127.0.0.1:<port>`.
  If nothing answers on the port and `autostart` is on, `chrome.ensure()` launches it (path auto-detected
  by `config.find_chrome()` unless set). ochi never closes the browser, only the tabs it opened for `fetch`/`snapshot`.
- Config: optional `ochi.toml` (template `ochi.example.toml`, not committed), env overrides
  `OCHI_CONFIG`, `OCHI_CHROME`, `OCHI_PROFILE`, `OCHI_PORT`, `OCHI_EXTRACTORS`; secrets in `.env`.
- Extractors live in `extractors/*.js` with a `// ==Extractor==` header (`@name`, `@match` glob, `@wait`, `@description`)
  and define `async function extract()`; `extractors.find()` prefers the longest specific match over the generic `*`.
- Discogs/Reddit DOM selectors are best-effort; when they break, take a `snapshot`, keep the HTML as a test fixture,
  fix the selector, add a test.
- Tool docstrings are read by any user's model: keep them neutral (no personal names).
- Do not add captcha solving, stealth evasion, or paywall bypass.
- Tests: `uv run pytest` (no network; `browser`-marked ones run extractors in headless Chromium against
  `tests/fixtures/`), lint: `uv run ruff check .`. CI: `.github/workflows/ci.yml`, Linux/macOS/Windows.
- Next ideas: packaging for `uvx`, Readability.js for `generic`, caching, more sites.
