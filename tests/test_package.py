"""The built wheel works on its own, the way `uvx` / `pip install` run it: outside the source checkout."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile

import pytest

from ochi import config

pytestmark = pytest.mark.skipif(not shutil.which("uv"), reason="needs uv on PATH")

CHECK = """
from ochi import config, extractors
assert not config.from_checkout(), config.CHECKOUT
names = {e.name for e in extractors.load_all()}
assert {"generic", "discogs-market", "reddit-thread", "reddit-sub"} <= names, names
assert extractors.find("https://www.reddit.com/r/x/comments/1/").name == "reddit-thread"
print("home", config.home())
"""


@pytest.fixture(scope="module")
def wheel(tmp_path_factory):
    out = tmp_path_factory.mktemp("dist")
    subprocess.run(["uv", "build", "--wheel", "--out-dir", str(out), str(config.CHECKOUT)],
                   check=True, capture_output=True)
    return next(out.glob("ochi-*.whl"))


def test_wheel_contains_extractors_and_examples(wheel):
    names = set(zipfile.ZipFile(wheel).namelist())
    for f in ("ochi/data/extractors/generic.js", "ochi/data/extractors/discogs-market.js",
              "ochi/data/ochi.example.toml", "ochi/data/env.example", "ochi/server.py"):
        assert f in names, f
    assert not any(n.startswith("tests/") or n.endswith(".env") for n in names)


def run_installed(wheel, cwd, *args, env=None):
    cmd = ["uv", "run", "--isolated", "--no-project", "--python", sys.executable, "--with", str(wheel), *args]
    return subprocess.run(cmd, cwd=cwd, env=env, check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout


def test_installed_copy_finds_its_extractors_and_inits_home(wheel, tmp_path):
    env = {**os.environ, "OCHI_HOME": str(tmp_path / "home")}
    out = run_installed(wheel, tmp_path, "python", "-c", CHECK, env=env)
    assert f"home {tmp_path / 'home'}" in out

    out = run_installed(wheel, tmp_path, "ochi", "init", env=env)
    assert out.count("created") == 2
    assert (tmp_path / "home" / "ochi.toml").is_file() and (tmp_path / "home" / ".env").is_file()
    assert (tmp_path / "home" / "extractors").is_dir()
