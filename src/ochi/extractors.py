"""Loading extractor scripts.

An extractor is a .js file in extractors/ with a Greasemonkey-style header:

    // ==Extractor==
    // @name   discogs-seller-shop
    // @match  https://www.discogs.com/seller/*
    // @wait   table
    // @require lib/Readability.js     (optional, repeatable: a library loaded before the code)
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

from . import config

HEADER = re.compile(r"//\s*==Extractor==(.*?)//\s*==/Extractor==", re.S)
FIELD = re.compile(r"//\s*@(\w+)\s+(.*)")


@dataclass
class Extractor:
    name: str
    path: Path
    matches: list[str] = field(default_factory=list)
    wait: str | None = None
    description: str = ""
    requires: list[str] = field(default_factory=list)
    code: str = ""

    def matches_url(self, url: str) -> bool:
        return any(fnmatch.fnmatchcase(url, m) for m in self.matches)


def builtin_dir() -> Path:
    return config.bundled("extractors")


def user_dir() -> Path:
    """Your own extractors: OCHI_EXTRACTORS, else extractors/ in ochi's home folder."""
    env = os.environ.get("OCHI_EXTRACTORS")
    return Path(env).expanduser() if env else config.home() / "extractors"


def load_all() -> list[Extractor]:
    """Built-in extractors, then the user's; a user extractor with the same @name replaces the built-in one."""
    by_name: dict[str, Extractor] = {}
    dirs = dict.fromkeys(d.resolve() for d in (builtin_dir(), user_dir()) if d.is_dir())
    for d in dirs:
        for ex in _load_dir(d):
            by_name[ex.name] = ex
    return sorted(by_name.values(), key=lambda e: e.name)


def _load_dir(directory: Path) -> list[Extractor]:
    result = []
    for path in sorted(directory.glob("*.js")):
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
            elif key == "require":
                ex.requires.append(val)
        ex.code = "\n".join([*(_library(directory, r) for r in ex.requires), text])
        result.append(ex)
    return result


def _library(directory: Path, name: str) -> str:
    """A @require'd file: next to the extractor, else among the built-in ones (so user extractors can use them)."""
    for base in (directory, builtin_dir()):
        path = (base / name).resolve()
        if path.is_relative_to(base.resolve()) and path.is_file():
            return path.read_text(encoding="utf-8")
    return f"throw new Error({f'ochi: @require {name} not found'!r});"


def find(url: str) -> Extractor | None:
    """First specific extractor whose @match fits; the generic one ('*') last."""
    all_ex = load_all()
    specific = [e for e in all_ex if e.matches_url(url) and "*" not in e.matches]
    if specific:
        # most specific pattern wins (r/*/comments/* beats r/*)
        def score(e: Extractor) -> int:
            return max(len(m) for m in e.matches if fnmatch.fnmatchcase(url, m))
        return max(specific, key=score)
    generic = [e for e in all_ex if "*" in e.matches]
    return generic[0] if generic else None
