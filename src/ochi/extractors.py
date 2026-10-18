"""Loading extractor scripts.

An extractor is a .js file in extractors/ with a Greasemonkey-style header:

    // ==Extractor==
    // @name   discogs-seller-shop
    // @match  https://www.discogs.com/seller/*
    // @wait   table
    // ==/Extractor==

and a body that defines `async function extract() { ... }` returning JSON.
The body runs inside the page, so fetch() carries the page's cookies.
"""
from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

HEADER = re.compile(r"//\s*==Extractor==(.*?)//\s*==/Extractor==", re.S)
FIELD = re.compile(r"//\s*@(\w+)\s+(.*)")


@dataclass
class Extractor:
    name: str
    path: Path
    matches: list[str] = field(default_factory=list)
    wait: str | None = None
    description: str = ""
    code: str = ""

    def matches_url(self, url: str) -> bool:
        return any(fnmatch.fnmatch(url, m) for m in self.matches)


def extractors_dir() -> Path:
    env = os.environ.get("OCHI_EXTRACTORS")
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parents[2] / "extractors"


def load_all() -> list[Extractor]:
    result = []
    for path in sorted(extractors_dir().glob("*.js")):
        text = path.read_text(encoding="utf-8")
        m = HEADER.search(text)
        if not m:
            continue
        ex = Extractor(name=path.stem, path=path, code=text)
        for line in m.group(1).splitlines():
            f = FIELD.search(line)
            if not f:
                continue
            key, val = f.group(1), f.group(2).strip()
            if key == "name":
                ex.name = val
            elif key == "match":
                ex.matches.append(val)
            elif key == "wait":
                ex.wait = val
            elif key == "description":
                ex.description = val
        result.append(ex)
    return result


def find(url: str) -> Extractor | None:
    """First specific extractor whose @match fits; the generic one ('*') last."""
    all_ex = load_all()
    specific = [e for e in all_ex if e.matches_url(url) and "*" not in e.matches]
    if specific:
        # most specific pattern wins (r/*/comments/* beats r/*)
        def score(e: Extractor) -> int:
            return max(len(m) for m in e.matches if fnmatch.fnmatch(url, m))
        return max(specific, key=score)
    generic = [e for e in all_ex if "*" in e.matches]
    return generic[0] if generic else None
