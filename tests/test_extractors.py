from __future__ import annotations

import pytest

from ochi import extractors


@pytest.mark.parametrize(("url", "name"), [
    ("https://www.discogs.com/seller/someone/profile?format=Vinyl", "discogs-market"),
    ("https://www.discogs.com/shop/list?genre=Rock", "discogs-market"),
    ("https://www.discogs.com/sell/release/123", "discogs-market"),
    ("https://www.discogs.com/de/seller/someone/profile", "discogs-market"),
    ("https://www.reddit.com/r/vinyl/comments/abc/some_title/", "reddit-thread"),
    ("https://old.reddit.com/r/vinyl/comments/abc/", "reddit-thread"),
    ("https://www.reddit.com/r/vinyl/", "reddit-sub"),
    ("https://example.com/article", "generic"),
    ("https://www.discogs.com/release/123", "generic"),
])
def test_bundled_extractors_routing(url, name):
    assert extractors.find(url).name == name


def test_bundled_extractors_have_headers():
    all_ex = extractors.load_all()
    assert {e.name for e in all_ex} >= {"generic", "discogs-market", "reddit-thread", "reddit-sub"}
    for e in all_ex:
        assert e.matches, e.name
        assert "async function extract" in e.code, e.name


def write(dir_, name, header, body="async function extract() { return 1; }"):
    (dir_ / f"{name}.js").write_text(f"// ==Extractor==\n{header}\n// ==/Extractor==\n{body}\n", encoding="utf-8")


@pytest.fixture
def ex_dir(tmp_path, monkeypatch):
    d = tmp_path / "extractors"
    d.mkdir()
    monkeypatch.setenv("OCHI_EXTRACTORS", str(d))
    return d


def test_header_fields(ex_dir):
    write(ex_dir, "file-name", "// @name  shop\n// @match https://a.test/*\n// @match https://b.test/*\n"
                               "// @wait  table.x, .y\n// @description Shop pages")
    ex = extractors.load_all()[0]
    assert ex.name == "shop"
    assert ex.matches == ["https://a.test/*", "https://b.test/*"]
    assert ex.wait == "table.x, .y"
    assert ex.description == "Shop pages"
    assert ex.path.name == "file-name.js"


def test_name_defaults_to_file_stem_and_headerless_files_are_skipped(ex_dir):
    write(ex_dir, "stem", "// @match https://a.test/*")
    (ex_dir / "helper.js").write_text("function notAnExtractor() {}", encoding="utf-8")
    assert [e.name for e in extractors.load_all()] == ["stem"]


def test_longest_match_wins_and_generic_is_fallback(ex_dir):
    write(ex_dir, "any", "// @match *")
    write(ex_dir, "sub", "// @match https://r.test/r/*")
    write(ex_dir, "thread", "// @match https://r.test/r/*/comments/*")
    assert extractors.find("https://r.test/r/x/comments/1").name == "thread"
    assert extractors.find("https://r.test/r/x").name == "sub"
    assert extractors.find("https://other.test/").name == "any"


def test_no_extractors(ex_dir):
    assert extractors.find("https://a.test/") is None
    write(ex_dir, "only", "// @match https://a.test/*")
    assert extractors.find("https://b.test/") is None


def test_match_is_case_sensitive_on_every_os(ex_dir):
    write(ex_dir, "a", "// @match https://a.test/Path/*")
    assert extractors.find("https://a.test/Path/1").name == "a"
    assert extractors.find("https://a.test/path/1") is None
