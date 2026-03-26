"""DuckDB query methods for market data storage."""

from datetime import datetime
from decimal import Decimal, InvalidOperation

import duckdb


class StockRepository:
    """Read/write interface over the DuckDB stocks and region_metadata tables."""

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self.conn = conn

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def insert_batch(
        self,
        region: str,
        rows: list[dict[str, str]],
        scraped_at: datetime,
    ) -> None:
        """Insert a list of stock dicts for a region under a single batch timestamp.

        Rows missing a valid numeric price are silently skipped.
        """
        # Store as naive UTC timestamp — TIMESTAMPTZ requires pytz which is optional
        ts = scraped_at.replace(tzinfo=None) if scraped_at.tzinfo else scraped_at

        records = []
        for row in rows:
            price_str = row.get("price", "").replace(",", "").strip()
            try:
                price = float(Decimal(price_str))
            except (InvalidOperation, ValueError):
                continue

            change_pct_str = row.get("change_pct", "").replace(",", "").strip()
            try:
                change_pct: float | None = (
                    float(Decimal(change_pct_str)) if change_pct_str else None
                )
            except (InvalidOperation, ValueError):
                change_pct = None

            records.append(
                (
                    region,
                    row.get("symbol", ""),
                    row.get("name", ""),
                    price,
                    change_pct,
                    ts,
                )
            )

        if records:
            self.conn.executemany(
                "INSERT INTO stocks (region, symbol, name, price, change_pct, scraped_at) VALUES (?, ?, ?, ?, ?, ?)",
                records,
            )

    def upsert_region_metadata(
        self,
        region: str,
        last_scraped_at: datetime,
        ttl_seconds: int = 14400,
    ) -> None:
        """Insert or update the metadata row for a region."""
        ts = last_scraped_at.replace(tzinfo=None) if last_scraped_at.tzinfo else last_scraped_at
        self.conn.execute(
            """
            INSERT INTO region_metadata (region, last_scraped_at, ttl_seconds, access_count)
            VALUES (?, ?, ?, 0)
            ON CONFLICT (region) DO UPDATE SET
                last_scraped_at = excluded.last_scraped_at,
                ttl_seconds     = excluded.ttl_seconds
            """,
            [region, ts, ttl_seconds],
        )

    def increment_access_count(self, region: str) -> None:
        """Increment the access counter for a region. No-ops if region is unknown."""
        self.conn.execute(
            "UPDATE region_metadata SET access_count = access_count + 1 WHERE region = ?",
            [region],
        )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_latest_by_region(self, region: str) -> list[dict]:
        """Return all rows from the most recent snapshot for a region."""
        result = self.conn.execute(
            """
            SELECT symbol, name, price, scraped_at
            FROM stocks
            WHERE region = ?
              AND scraped_at = (
                  SELECT MAX(scraped_at) FROM stocks WHERE region = ?
              )
            ORDER BY price DESC
            """,
            [region, region],
        ).fetchall()

        return [
            {"symbol": r[0], "name": r[1], "price": float(r[2]), "scraped_at": r[3].isoformat()}
            for r in result
        ]

    def get_region_metadata(self, region: str) -> dict | None:
        """Return metadata dict for a region, or None if not found."""
        row = self.conn.execute(
            "SELECT region, last_scraped_at, access_count, ttl_seconds FROM region_metadata WHERE region = ?",
            [region],
        ).fetchone()

        if row is None:
            return None

        return {
            "region": row[0],
            "last_scraped_at": row[1].isoformat() if row[1] else None,
            "access_count": row[2],
            "ttl_seconds": row[3],
        }

    def get_top_movers(self, region: str, n: int = 10, sort_by: str = "price") -> list[dict]:
        """Return the top N stocks from the latest snapshot, sorted by price or change_pct."""
        order_col = "change_pct" if sort_by == "change_pct" else "price"
        result = self.conn.execute(
            f"""
            SELECT symbol, name, price, change_pct
            FROM stocks
            WHERE region = ?
              AND scraped_at = (
                  SELECT MAX(scraped_at) FROM stocks WHERE region = ?
              )
              AND {order_col} IS NOT NULL
            ORDER BY {order_col} DESC
            LIMIT ?
            """,
            [region, region, n],
        ).fetchall()

        return [
            {
                "symbol": r[0],
                "name": r[1],
                "price": float(r[2]) if r[2] is not None else None,
                "change_pct": float(r[3]) if r[3] is not None else None,
            }
            for r in result
        ]

    def get_count_by_region(self, region: str) -> int:
        """Return the number of stocks in the latest snapshot for a region."""
        row = self.conn.execute(
            """
            SELECT COUNT(*) FROM stocks
            WHERE region = ?
              AND scraped_at = (SELECT MAX(scraped_at) FROM stocks WHERE region = ?)
            """,
            [region, region],
        ).fetchone()
        return row[0] if row else 0

    def search_symbol(self, symbol: str) -> list[dict]:
        """Search for a symbol (case-insensitive partial match) across all regions.

        Returns the most recent row per (region, symbol) pair.
        """
        result = self.conn.execute(
            """
            SELECT s.region, s.symbol, s.name, s.price, s.scraped_at
            FROM stocks s
            INNER JOIN (
                SELECT region, symbol, MAX(scraped_at) AS max_ts
                FROM stocks
                WHERE symbol ILIKE ?
                GROUP BY region, symbol
            ) latest ON s.region = latest.region
                     AND s.symbol = latest.symbol
                     AND s.scraped_at = latest.max_ts
            ORDER BY s.region, s.symbol
            """,
            [f"%{symbol}%"],
        ).fetchall()

        return [
            {
                "region": r[0],
                "symbol": r[1],
                "name": r[2],
                "price": float(r[3]),
                "scraped_at": r[4].isoformat(),
            }
            for r in result
        ]

    def get_aggregated_for_ai(self, region: str, limit: int = 50) -> list[dict]:
        """Return top N rows from the latest snapshot, ranked by price, for the AI layer.

        Capped at `limit` rows and restricted to the most recent scrape batch only.
        This keeps AI token usage predictable regardless of region size.
        """
        result = self.conn.execute(
            """
            SELECT symbol, name, price, scraped_at
            FROM stocks
            WHERE region = ?
              AND scraped_at = (
                  SELECT MAX(scraped_at) FROM stocks WHERE region = ?
              )
            ORDER BY price DESC
            LIMIT ?
            """,
            [region, region, limit],
        ).fetchall()

        return [
            {"symbol": r[0], "name": r[1], "price": float(r[2]), "scraped_at": r[3].isoformat()}
            for r in result
        ]
