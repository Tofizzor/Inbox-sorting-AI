"""Shared test fixtures.

`mock_client` gives each test an isolated SQLite file and the deterministic offline
`mock` LLM provider, so the whole reply flow is exercised end to end without a live model.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def mock_client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    import db.database as database
    from config import get_settings

    db_path = tmp_path / "test.db"
    monkeypatch.setattr(database, "get_database_path", lambda: db_path)

    monkeypatch.setenv("LLM_PROVIDER", "mock")
    get_settings.cache_clear()

    from main import app

    # Entering the context runs the lifespan init_db() against the patched temp DB.
    with TestClient(app) as client:
        yield client

    get_settings.cache_clear()
