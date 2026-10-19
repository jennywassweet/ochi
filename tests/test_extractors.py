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
    """The user's extractors folder, with the built-in ones out of the way."""
    d = tmp_path / "extractors"
    d.mkdir()
    monkeypatch.setenv("OCHI_EXTRACTORS", str(d))
    monkeypatch.setattr(extractors, "builtin_dir", lambda: tmp_path / "no-builtins")
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


def test_user_extractors_add_to_and_replace_builtins(tmp_path, monkeypatch):
    home = tmp_path / "ochi-home"  # OCHI_HOME from conftest
    (home / "extractors").mkdir(parents=True)
    write(home / "extractors", "my-generic", "// @name generic\n// @match *\n// @description mine")
    write(home / "extractors", "shop", "// @match https://shop.test/*")
    by_name = {e.name: e for e in extractors.load_all()}
    assert by_name["generic"].description == "mine"
    assert "discogs-market" in by_name and "shop" in by_name
    assert extractors.find("https://shop.test/x").name == "shop"


def test_same_folder_is_loaded_once(monkeypatch):
    monkeypatch.setenv("OCHI_EXTRACTORS", str(extractors.builtin_dir()))
    names = [e.name for e in extractors.load_all()]
    assert len(names) == len(set(names))


def test_require_loads_libraries_before_the_code(ex_dir):
    (ex_dir / "lib").mkdir()
    (ex_dir / "lib" / "helper.js").write_text("function helper() { return 1; }", encoding="utf-8")
    write(ex_dir, "uses", "// @match https://a.test/*\n// @require lib/helper.js")
    ex = extractors.load_all()[0]
    assert ex.requires == ["lib/helper.js"]
    assert ex.code.index("function helper") < ex.code.index("async function extract")


def test_require_falls_back_to_builtin_libraries(ex_dir, monkeypatch, tmp_path):
    builtin = tmp_path / "builtin"
    (builtin / "lib").mkdir(parents=True)
    (builtin / "lib" / "shared.js").write_text("function shared() {}", encoding="utf-8")
    monkeypatch.setattr(extractors, "builtin_dir", lambda: builtin)
    write(ex_dir, "mine", "// @match https://a.test/*\n// @require lib/shared.js")
    assert "function shared" in {e.name: e for e in extractors.load_all()}["mine"].code


@pytest.mark.parametrize("name", ["lib/missing.js", "../../../etc/passwd"])
def test_require_missing_or_outside_fails_loudly_when_run(ex_dir, name):
    write(ex_dir, "broken", f"// @match https://a.test/*\n// @require {name}")
    code = extractors.load_all()[0].code
    assert code.startswith("throw new Error(") and "not found" in code.splitlines()[0]
    assert "root:" not in code


def test_generic_bundles_readability():
    g = extractors.find("https://example.com/")
    assert g.requires == ["lib/Readability-readerable.js", "lib/Readability.js"]
    assert "function Readability(" in g.code and "function isProbablyReaderable(" in g.code
