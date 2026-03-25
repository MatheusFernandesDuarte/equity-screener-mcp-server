"""DuckDB connection management and schema bootstrap."""

import duckdb


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


def get_connection(db_path: str = "data/market.duckdb") -> duckdb.DuckDBPyConnection:
    """Open (or create) a persistent DuckDB database and bootstrap the schema."""
    import os
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = duckdb.connect(db_path)
    bootstrap_schema(conn)
    return conn
