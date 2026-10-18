# Contributing to ochi

Thanks for wanting to help! ochi is a small personal project, maintained in spare time:
issues and pull requests are welcome, but answers may take a while and not every idea will be merged.

## The most useful contributions

- **A site changed and its extractor broke.** These breakages are expected: sites change their pages.
  A fix with a fresh fixture is the best kind of PR.
- **An extractor for a new site.** Especially sites that block plain HTTP fetching or bury their content in markup.
- **Bug reports** with the URL (or URL pattern), what you expected, what you got, and your OS.

For bigger changes (new tools, new dependencies, changes to how the browser is driven) please open an
issue first, so we can agree on the approach before you spend time on it.

## Setup

```sh
git clone https://github.com/jennywassweet/ochi && cd ochi
uv sync
uv run playwright install chromium   # once; otherwise browser tests use an installed Chrome
uv run pytest
uv run ruff check .
```

When run from a clone, ochi keeps `ochi.toml`, `.env`, `snapshots/` in the repo folder and reads
extractors from `extractors/`. Try a page with `uv run ochi-try <url>`.

## Fixing or adding an extractor

1. Take a snapshot of the page: `uv run ochi-try --snapshot <url>` (saved to `snapshots/`).
2. Put a cleaned copy into `tests/fixtures/`, see its `README.md`. **Before committing, strip scripts,
   styles and anything tied to your account** (username, user id, cart, wantlist, tokens, cookies).
   A small hand-made page with just the markup the extractor reads is fine too, note it as synthetic.
3. Write or fix `extractors/<site>.js`. The header (`@name`, `@match`, `@wait`, `@description`) and
   `async function extract()` are described in the README.
4. Add a test to `tests/test_extractors_js.py`. Tests serve the fixture through a route, so they never
   touch the network.
5. Check it on the live site once with `ochi-try`, and mention in the PR that you did.

## Ground rules

- **Not accepted:** captcha solving, stealth or bot-detection evasion, paywall bypass, logging into
  accounts on the user's behalf. If a site asks for a human, the human clicks.
- Extractors run inside the user's logged-in browser. Keep them read-only: no clicks that change state,
  no form submissions, no requests to other sites.
- Be gentle with sites: few requests, pauses between pages (see `discogs-market.js`).
- Tests must pass without network access, on Linux, macOS and Windows (CI checks all three).
- Tool docstrings are read by every user's model: keep them neutral and short.

## Pull requests

Keep PRs focused on one change, describe what and why, and make sure `uv run pytest` and
`uv run ruff check .` pass. By contributing you agree that your work is released under the
[MIT License](LICENSE).
