"""DuckDB connection management and schema bootstrap."""

import os
from pathlib import Path

import duckdb

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_DB_PATH = str(_PROJECT_ROOT / "data" / "market.duckdb")


def bootstrap_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create tables and indexes if they do not already exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            region     VARCHAR      NOT NULL,
            symbol     VARCHAR      NOT NULL,
            name       VARCHAR,
            price      DECIMAL(18, 4),
            scraped_at TIMESTAMP    NOT NULL
        )
    """)

    # Add change_pct column if upgrading from an older schema
    conn.execute("""
        ALTER TABLE stocks ADD COLUMN IF NOT EXISTS change_pct DECIMAL(10, 4)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_stocks_region_time
        ON stocks (region, scraped_at DESC)
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS region_metadata (
            region          VARCHAR PRIMARY KEY,
            last_scraped_at TIMESTAMP,
            access_count    BIGINT  DEFAULT 0,
            ttl_seconds     INTEGER DEFAULT 14400
        )
    """)


def get_connection(db_path: str | None = None) -> duckdb.DuckDBPyConnection:
    """Open (or create) a persistent DuckDB database and bootstrap the schema."""
    resolved = db_path or os.getenv("DUCKDB_PATH") or _DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(resolved), exist_ok=True)
    conn = duckdb.connect(resolved)
    bootstrap_schema(conn)
    return conn


def bootstrap_db(db_path: str | None = None) -> duckdb.DuckDBPyConnection:
    """Alias for get_connection — used in tests and CLI."""
    return get_connection(db_path)
