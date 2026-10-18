# ochi — notes for coding agents

- Python ≥3.11, managed with `uv`. Run: `uv run ochi` (MCP stdio), `uv run ochi-try <url>` (manual).
- `mcp` is pinned `<2` (we use `mcp.server.fastmcp.FastMCP`).
- Browser is NOT launched by ochi: it attaches to the user's running Chrome via CDP (`OCHI_CDP`, default `http://localhost:9222`) and never closes it, only its own tabs.
- Extractors live in `extractors/*.js` with a `// ==Extractor==` header (`@name`, `@match` glob, `@wait`, `@description`) and define `async function extract()`; `extractors.find()` prefers specific matches over the generic `*`.
- Discogs/Reddit DOM selectors are best-effort; when they break, take a `snapshot`, put the HTML in `tests/fixtures/`, fix the selector, add a test.
- Do not add captcha solving, stealth evasion, or paywall bypass.
- Next ideas: Readability.js for `generic`, tests with saved HTML fixtures, caching, more sites.
