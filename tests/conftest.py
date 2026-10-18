from __future__ import annotations

import pytest

from ochi import config

@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    """No user config, .env or tokens leak into tests; config cache is fresh."""
    for var in ("OCHI_CONFIG", "OCHI_CHROME", "OCHI_PROFILE", "OCHI_PORT", "OCHI_EXTRACTORS",
                "DISCOGS_TOKEN", "DISCOGS_PERSONAL_ACCESS_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OCHI_CONFIG", str(tmp_path / "no-such-ochi.toml"))
    config.load.cache_clear()
    yield
    config.load.cache_clear()


@pytest.fixture
def anyio_backend():
    return "asyncio"
