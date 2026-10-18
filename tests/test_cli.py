from __future__ import annotations

import sys

import pytest

from ochi import browser, cli, config


def run_cli(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["ochi-try", *args])
    cli.main()


@pytest.mark.parametrize("args", [(), ("--snapshot",)])
def test_usage(monkeypatch, capsys, args):
    with pytest.raises(SystemExit) as e:
        run_cli(monkeypatch, *args)
    assert e.value.code == 1
    assert "ochi-try" in capsys.readouterr().out


def test_no_extractor(monkeypatch, tmp_path):
    from ochi import extractors
    monkeypatch.setattr(extractors, "builtin_dir", lambda: tmp_path / "none")
    with pytest.raises(SystemExit) as e:
        run_cli(monkeypatch, "https://a.test/")
    assert "No extractor" in str(e.value.code)


def test_fetch_prints_extractor_and_result(monkeypatch, capsys):
    async def run(url, ex):
        return f"{ex.name} read {url} 📌"

    monkeypatch.setattr(browser, "run", run)
    run_cli(monkeypatch, "https://example.com/")
    assert capsys.readouterr().out == "[extractor: generic]\ngeneric read https://example.com/ 📌\n"


def test_snapshot_goes_to_project_dir(monkeypatch, capsys):
    seen = {}

    async def snapshot(url, out_dir):
        seen["dir"] = out_dir
        return out_dir / "x.html"

    monkeypatch.setattr(browser, "snapshot", snapshot)
    run_cli(monkeypatch, "--snapshot", "https://example.com/")
    assert seen["dir"] == config.home() / "snapshots"


def test_init_creates_home_and_keeps_existing_files(monkeypatch, capsys):
    home = config.home()
    from ochi import server
    monkeypatch.setattr(sys, "argv", ["ochi", "init"])
    server.main()
    assert (home / "extractors").is_dir()
    assert "[chrome]" in (home / "ochi.toml").read_text(encoding="utf-8")
    assert "DISCOGS_TOKEN=" in (home / ".env").read_text(encoding="utf-8")
    assert capsys.readouterr().out.count("created") == 2

    (home / ".env").write_text("DISCOGS_TOKEN=mine\n", encoding="utf-8")
    server.main()
    assert (home / ".env").read_text(encoding="utf-8") == "DISCOGS_TOKEN=mine\n"
    assert capsys.readouterr().out.count("kept") == 2
