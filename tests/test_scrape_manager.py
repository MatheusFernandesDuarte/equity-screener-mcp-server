"""Tests for ScrapeManager.

No live browser, no real DuckDB — all dependencies are mocked.
Threading behaviour is validated using Events and short timeouts.
"""

import threading
import time
from unittest.mock import MagicMock, call

import pytest

from src.scraper.manager import ScrapeManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_manager(scrape_rows=None, max_workers=1):
    """Return a ScrapeManager with a mock engine factory and mock repository."""
    if scrape_rows is None:
        scrape_rows = [{"symbol": "X", "name": "X Co", "price": "10.0"}]

    mock_engine = MagicMock()
    mock_engine.scrape.return_value = scrape_rows

    engine_factory = MagicMock(return_value=mock_engine)

    mock_repo = MagicMock()

    manager = ScrapeManager(
        engine_factory=engine_factory,
        repository=mock_repo,
        max_workers=max_workers,
    )
    return manager, engine_factory, mock_engine, mock_repo


# ---------------------------------------------------------------------------
# submit() — deduplication
# ---------------------------------------------------------------------------

def test_submit_returns_true_for_new_region():
    manager, *_ = make_manager()
    result = manager.submit("Argentina")
    assert result is True
    manager.shutdown()


def test_submit_returns_false_for_duplicate_region():
    manager, engine_factory, mock_engine, mock_repo = make_manager()

    # Block the worker so the region stays in in_progress
    started = threading.Event()
    released = threading.Event()

    def slow_scrape(region):
        started.set()
        released.wait(timeout=5)
        return []

    mock_engine.scrape.side_effect = slow_scrape

    manager.submit("Argentina")
    started.wait(timeout=2)       # wait until worker is executing

    second = manager.submit("Argentina")  # duplicate — must return False
    assert second is False

    released.set()
    manager.shutdown()


def test_submit_allows_different_regions_concurrently():
    manager, *_ = make_manager(max_workers=2)
    r1 = manager.submit("Argentina")
    r2 = manager.submit("Belgium")
    assert r1 is True
    assert r2 is True
    manager.shutdown()


def test_submit_marks_region_before_enqueue():
    """Region must be in in_progress immediately after submit(), before worker starts."""
    manager, engine_factory, mock_engine, _ = make_manager()

    started = threading.Event()
    released = threading.Event()

    def blocking_scrape(region):
        started.set()
        released.wait(timeout=5)
        return []

    mock_engine.scrape.side_effect = blocking_scrape

    manager.submit("Argentina")
    started.wait(timeout=2)

    assert "Argentina" in manager._in_progress

    released.set()
    manager.shutdown()


def test_region_removed_from_in_progress_after_completion():
    manager, *_ = make_manager()
    manager.submit("Argentina")

    deadline = time.time() + 3
    while time.time() < deadline:
        if "Argentina" not in manager._in_progress:
            break
        time.sleep(0.05)

    assert "Argentina" not in manager._in_progress
    manager.shutdown()


def test_region_removed_even_when_scrape_raises():
    manager, engine_factory, mock_engine, _ = make_manager()
    mock_engine.scrape.side_effect = RuntimeError("boom")

    manager.submit("Argentina")

    deadline = time.time() + 3
    while time.time() < deadline:
        if "Argentina" not in manager._in_progress:
            break
        time.sleep(0.05)

    assert "Argentina" not in manager._in_progress
    manager.shutdown()


# ---------------------------------------------------------------------------
# Worker — scrape + persist
# ---------------------------------------------------------------------------

def test_worker_calls_engine_scrape_with_region():
    manager, engine_factory, mock_engine, mock_repo = make_manager()
    done = threading.Event()
    mock_repo.insert_batch.side_effect = lambda *a, **kw: done.set()

    manager.submit("Belgium")
    done.wait(timeout=3)

    mock_engine.scrape.assert_called_once_with("Belgium")
    manager.shutdown()


def test_worker_calls_insert_batch_with_scraped_rows():
    rows = [{"symbol": "ABI.BR", "name": "AB InBev", "price": "55.86"}]
    manager, engine_factory, mock_engine, mock_repo = make_manager(scrape_rows=rows)
    done = threading.Event()
    mock_repo.upsert_region_metadata.side_effect = lambda *a, **kw: done.set()

    manager.submit("Belgium")
    done.wait(timeout=3)

    assert mock_repo.insert_batch.called
    call_args = mock_repo.insert_batch.call_args
    assert call_args[0][0] == "Belgium"
    assert call_args[0][1] == rows
    manager.shutdown()


def test_worker_calls_upsert_region_metadata():
    manager, engine_factory, mock_engine, mock_repo = make_manager()
    done = threading.Event()
    mock_repo.upsert_region_metadata.side_effect = lambda *a, **kw: done.set()

    manager.submit("Belgium")
    done.wait(timeout=3)

    assert mock_repo.upsert_region_metadata.called
    manager.shutdown()


def test_worker_creates_engine_via_factory():
    manager, engine_factory, mock_engine, mock_repo = make_manager()
    done = threading.Event()
    mock_repo.upsert_region_metadata.side_effect = lambda *a, **kw: done.set()

    manager.submit("Argentina")
    done.wait(timeout=3)

    engine_factory.assert_called_once()
    manager.shutdown()


def test_worker_closes_driver_after_scrape():
    manager, engine_factory, mock_engine, mock_repo = make_manager()
    done = threading.Event()
    mock_repo.upsert_region_metadata.side_effect = lambda *a, **kw: done.set()

    manager.submit("Argentina")
    done.wait(timeout=3)

    mock_engine.driver.quit.assert_called_once()
    manager.shutdown()


def test_worker_closes_driver_even_when_scrape_raises():
    manager, engine_factory, mock_engine, _ = make_manager()
    mock_engine.scrape.side_effect = RuntimeError("network error")

    manager.submit("Argentina")

    deadline = time.time() + 3
    while time.time() < deadline:
        if "Argentina" not in manager._in_progress:
            break
        time.sleep(0.05)

    mock_engine.driver.quit.assert_called_once()
    manager.shutdown()


# ---------------------------------------------------------------------------
# Resubmit after completion
# ---------------------------------------------------------------------------

def test_region_can_be_resubmitted_after_completion():
    manager, engine_factory, mock_engine, mock_repo = make_manager()
    done = threading.Event()

    call_count = {"n": 0}

    def track_and_signal(*a, **kw):
        call_count["n"] += 1
        if call_count["n"] >= 2:
            done.set()

    mock_repo.upsert_region_metadata.side_effect = track_and_signal

    manager.submit("Argentina")
    # Wait for first scrape to finish then submit again
    time.sleep(0.3)
    manager.submit("Argentina")
    done.wait(timeout=5)

    assert mock_engine.scrape.call_count == 2
    manager.shutdown()
