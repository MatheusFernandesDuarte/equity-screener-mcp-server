"""Tests for the DuckDB storage layer (database + repository).

All tests use an in-memory DuckDB connection — no file I/O, no side effects.
"""

from datetime import datetime, timezone

import pytest

from src.storage.database import bootstrap_schema
from src.storage.repository import StockRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def repo():
    """Return a StockRepository backed by an in-memory DuckDB instance."""
    import duckdb
    conn = duckdb.connect(":memory:")
    bootstrap_schema(conn)
    return StockRepository(conn)


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

def test_bootstrap_creates_stocks_table(repo):
    tables = {row[0] for row in repo.conn.execute("SHOW TABLES").fetchall()}
    assert "stocks" in tables
    assert "region_metadata" in tables


# ---------------------------------------------------------------------------
# insert_batch
# ---------------------------------------------------------------------------

def test_insert_batch_writes_rows(repo):
    rows = [
        {"symbol": "AAPL.BA", "name": "Apple Inc.", "price": "150.00"},
        {"symbol": "MSFT.BA", "name": "Microsoft", "price": "320.50"},
    ]
    scraped_at = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)
    repo.insert_batch("Argentina", rows, scraped_at)

    count = repo.conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
    assert count == 2


def test_insert_batch_stores_correct_values(repo):
    rows = [{"symbol": "AAPL.BA", "name": "Apple Inc.", "price": "150.00"}]
    scraped_at = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)
    repo.insert_batch("Argentina", rows, scraped_at)

    row = repo.conn.execute("SELECT region, symbol, name, price FROM stocks").fetchone()
    assert row[0] == "Argentina"
    assert row[1] == "AAPL.BA"
    assert row[2] == "Apple Inc."
    assert float(row[3]) == 150.00


def test_insert_batch_skips_rows_with_no_price(repo):
    rows = [
        {"symbol": "AAPL.BA", "name": "Apple Inc.", "price": ""},
        {"symbol": "MSFT.BA", "name": "Microsoft", "price": "320.50"},
    ]
    scraped_at = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)
    repo.insert_batch("Argentina", rows, scraped_at)

    count = repo.conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
    assert count == 1


def test_insert_batch_multiple_regions_isolated(repo):
    scraped_at = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)
    repo.insert_batch("Argentina", [{"symbol": "A", "name": "A Co", "price": "10.0"}], scraped_at)
    repo.insert_batch("Belgium", [{"symbol": "B", "name": "B Co", "price": "20.0"}], scraped_at)

    arg = repo.conn.execute("SELECT COUNT(*) FROM stocks WHERE region='Argentina'").fetchone()[0]
    bel = repo.conn.execute("SELECT COUNT(*) FROM stocks WHERE region='Belgium'").fetchone()[0]
    assert arg == 1
    assert bel == 1


# ---------------------------------------------------------------------------
# get_latest_by_region
# ---------------------------------------------------------------------------

def test_get_latest_by_region_returns_most_recent_snapshot(repo):
    old_ts = datetime(2026, 3, 24, 0, 0, 0, tzinfo=timezone.utc)
    new_ts = datetime(2026, 3, 25, 0, 0, 0, tzinfo=timezone.utc)

    repo.insert_batch("Argentina", [{"symbol": "OLD", "name": "Old", "price": "1.0"}], old_ts)
    repo.insert_batch("Argentina", [{"symbol": "NEW", "name": "New", "price": "2.0"}], new_ts)

    results = repo.get_latest_by_region("Argentina")
    assert len(results) == 1
    assert results[0]["symbol"] == "NEW"


def test_get_latest_by_region_returns_all_rows_from_latest_snapshot(repo):
    ts = datetime(2026, 3, 25, 0, 0, 0, tzinfo=timezone.utc)
    rows = [
        {"symbol": "A", "name": "A Co", "price": "10.0"},
        {"symbol": "B", "name": "B Co", "price": "20.0"},
        {"symbol": "C", "name": "C Co", "price": "30.0"},
    ]
    repo.insert_batch("Belgium", rows, ts)

    results = repo.get_latest_by_region("Belgium")
    assert len(results) == 3


def test_get_latest_by_region_returns_empty_for_unknown_region(repo):
    results = repo.get_latest_by_region("Narnia")
    assert results == []


# ---------------------------------------------------------------------------
# region_metadata — upsert + read
# ---------------------------------------------------------------------------

def test_upsert_region_metadata_creates_row(repo):
    ts = datetime(2026, 3, 25, 0, 0, 0, tzinfo=timezone.utc)
    repo.upsert_region_metadata("Argentina", last_scraped_at=ts, ttl_seconds=3600)

    row = repo.conn.execute(
        "SELECT region, ttl_seconds FROM region_metadata WHERE region='Argentina'"
    ).fetchone()
    assert row is not None
    assert row[0] == "Argentina"
    assert row[1] == 3600


def test_upsert_region_metadata_updates_existing_row(repo):
    ts1 = datetime(2026, 3, 24, 0, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2026, 3, 25, 0, 0, 0, tzinfo=timezone.utc)
    repo.upsert_region_metadata("Argentina", ts1, ttl_seconds=14400)
    repo.upsert_region_metadata("Argentina", ts2, ttl_seconds=3600)

    count = repo.conn.execute("SELECT COUNT(*) FROM region_metadata").fetchone()[0]
    assert count == 1

    ttl = repo.conn.execute(
        "SELECT ttl_seconds FROM region_metadata WHERE region='Argentina'"
    ).fetchone()[0]
    assert ttl == 3600


def test_get_region_metadata_returns_none_for_unknown(repo):
    result = repo.get_region_metadata("Narnia")
    assert result is None


def test_get_region_metadata_returns_dict(repo):
    ts = datetime(2026, 3, 25, 0, 0, 0, tzinfo=timezone.utc)
    repo.upsert_region_metadata("Belgium", ts, ttl_seconds=7200)

    meta = repo.get_region_metadata("Belgium")
    assert meta is not None
    assert meta["region"] == "Belgium"
    assert meta["ttl_seconds"] == 7200
    assert meta["access_count"] == 0


# ---------------------------------------------------------------------------
# increment_access_count
# ---------------------------------------------------------------------------

def test_increment_access_count_increases_counter(repo):
    ts = datetime(2026, 3, 25, 0, 0, 0, tzinfo=timezone.utc)
    repo.upsert_region_metadata("Argentina", ts, ttl_seconds=3600)
    repo.increment_access_count("Argentina")
    repo.increment_access_count("Argentina")

    meta = repo.get_region_metadata("Argentina")
    assert meta["access_count"] == 2


def test_increment_access_count_no_ops_on_missing_region(repo):
    # Must not raise — region simply doesn't exist yet
    repo.increment_access_count("Narnia")


# ---------------------------------------------------------------------------
# get_top_movers
# ---------------------------------------------------------------------------

def test_get_top_movers_returns_n_highest_price(repo):
    ts = datetime(2026, 3, 25, 0, 0, 0, tzinfo=timezone.utc)
    rows = [{"symbol": str(i), "name": f"Co {i}", "price": str(float(i * 10))} for i in range(1, 6)]
    repo.insert_batch("Belgium", rows, ts)

    top = repo.get_top_movers("Belgium", n=3)
    assert len(top) == 3
    assert top[0]["symbol"] == "5"   # highest price first


def test_get_top_movers_returns_empty_for_unknown_region(repo):
    assert repo.get_top_movers("Narnia", n=5) == []


# ---------------------------------------------------------------------------
# search_symbol
# ---------------------------------------------------------------------------

def test_search_symbol_finds_exact_match(repo):
    ts = datetime(2026, 3, 25, 0, 0, 0, tzinfo=timezone.utc)
    repo.insert_batch("Argentina", [{"symbol": "AAPL.BA", "name": "Apple", "price": "150.0"}], ts)

    results = repo.search_symbol("AAPL.BA")
    assert len(results) == 1
    assert results[0]["symbol"] == "AAPL.BA"


def test_search_symbol_finds_partial_match(repo):
    ts = datetime(2026, 3, 25, 0, 0, 0, tzinfo=timezone.utc)
    repo.insert_batch("Argentina", [{"symbol": "AAPL.BA", "name": "Apple", "price": "150.0"}], ts)
    repo.insert_batch("Belgium", [{"symbol": "AAPL.BR", "name": "Apple Belgium", "price": "155.0"}], ts)

    results = repo.search_symbol("AAPL")
    symbols = {r["symbol"] for r in results}
    assert "AAPL.BA" in symbols
    assert "AAPL.BR" in symbols


def test_search_symbol_is_case_insensitive(repo):
    ts = datetime(2026, 3, 25, 0, 0, 0, tzinfo=timezone.utc)
    repo.insert_batch("Argentina", [{"symbol": "AAPL.BA", "name": "Apple", "price": "150.0"}], ts)

    results = repo.search_symbol("aapl")
    assert len(results) >= 1


def test_search_symbol_returns_empty_for_no_match(repo):
    assert repo.search_symbol("ZZZZ") == []
