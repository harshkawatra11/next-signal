import pytest

from next_signal import store as store_module
from next_signal.config import settings


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    """Every test gets its own throwaway SQLite file and a fresh store connection, so a test that
    touches next_signal.store (directly, or indirectly through events.bus, which always writes
    through store.append_event) never reads or writes the real engine/data/next_signal.sqlite file.
    Without this, a prior session's live run data could leak into a test's assertions, and a test's
    own writes permanently pollute that file: two stray run_ids, r4 and r6, were found in the real
    database, written by tests/test_pipeline_prove.py's respx-mocked writer tests before this
    fixture existed, since those tests call prove.run() for real and it calls the real bus."""
    monkeypatch.setattr(settings, "db_path", tmp_path / "test_next_signal.sqlite")
    monkeypatch.setattr(store_module, "_conn", None)
    yield
    monkeypatch.setattr(store_module, "_conn", None)
