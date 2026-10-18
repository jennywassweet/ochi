from __future__ import annotations

import os
import sys
from pathlib import Path

from ochi import chrome, config


def test_defaults_without_file(monkeypatch):
    monkeypatch.setattr(config, "find_chrome", lambda: "/found/chrome")
    c = config.load()["chrome"]
    assert c["path"] == "/found/chrome"
    assert c["profile"] == "~/.ochi-profile"
    assert c["port"] == 9222
    assert c["autostart"] is True
    assert "--no-first-run" in c["args"]
    assert chrome.cdp_url() == "http://127.0.0.1:9222"


def test_file_values_and_env_overrides(tmp_path, monkeypatch):
    toml = tmp_path / "ochi.toml"
    toml.write_text('[chrome]\npath = "/from/file"\nport = 9333\nautostart = false\nargs = []\n', encoding="utf-8")
    monkeypatch.setenv("OCHI_CONFIG", str(toml))
    c = config.load()["chrome"]
    assert (c["path"], c["port"], c["autostart"], c["args"]) == ("/from/file", 9333, False, [])

    config.load.cache_clear()
    monkeypatch.setenv("OCHI_CHROME", "/from/env")
    monkeypatch.setenv("OCHI_PROFILE", "/tmp/prof")
    monkeypatch.setenv("OCHI_PORT", "9444")
    c = config.load()["chrome"]
    assert (c["path"], c["profile"], c["port"]) == ("/from/env", "/tmp/prof", 9444)


def test_find_chrome_on_path(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(config.shutil, "which", lambda cmd: f"/usr/bin/{cmd}" if cmd == "chromium" else None)
    assert config.find_chrome() == "/usr/bin/chromium"


def test_find_chrome_windows_install_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(config.shutil, "which", lambda cmd: None)
    for var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    exe = tmp_path / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    exe.parent.mkdir(parents=True)
    exe.touch()
    assert os.path.samefile(config.find_chrome(), exe)


def test_find_chrome_nothing(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(config.shutil, "which", lambda cmd: None)
    assert config.find_chrome() is None


def test_load_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "# comment\n\nOCHI_T_A=1\nOCHI_T_B = 'quoted value'\nOCHI_T_C=\"x=y\"\nnot a pair\nOCHI_T_KEEP=file\n",
        encoding="utf-8")
    monkeypatch.setenv("OCHI_HOME", str(tmp_path))
    monkeypatch.setenv("OCHI_T_KEEP", "env")
    for k in ("OCHI_T_A", "OCHI_T_B", "OCHI_T_C"):
        monkeypatch.delenv(k, raising=False)
    config.load_dotenv()
    assert os.environ["OCHI_T_A"] == "1"
    assert os.environ["OCHI_T_B"] == "quoted value"
    assert os.environ["OCHI_T_C"] == "x=y"
    assert os.environ["OCHI_T_KEEP"] == "env"


def test_load_dotenv_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("OCHI_HOME", str(tmp_path))
    config.load_dotenv()  # no error


def test_home_is_ochi_home_then_checkout_then_user_dir(tmp_path, monkeypatch):
    assert config.home() == tmp_path / "ochi-home"  # OCHI_HOME from conftest
    monkeypatch.delenv("OCHI_HOME")
    assert config.from_checkout()  # tests run from the repo
    assert config.home() == config.CHECKOUT
    monkeypatch.setattr(config, "CHECKOUT", tmp_path / "site-packages")
    assert config.home() == config.user_dir()


def test_config_file_is_read_from_home(tmp_path):
    home = tmp_path / "ochi-home"
    home.mkdir()
    (home / "ochi.toml").write_text("[chrome]\nport = 9555\n", encoding="utf-8")
    assert config.load()["chrome"]["port"] == 9555


def test_user_dir_per_os(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert config.user_dir() == tmp_path / "Roaming" / "ochi"
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert config.user_dir() == tmp_path / "xdg" / "ochi"
    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert config.user_dir() == Path.home() / ".config" / "ochi"
    monkeypatch.setattr(sys, "platform", "darwin")
    assert config.user_dir() == Path.home() / "Library" / "Application Support" / "ochi"


def test_bundled_files_exist():
    for name in ("extractors", "ochi.example.toml", ".env.example"):
        assert config.bundled(name).exists(), name
