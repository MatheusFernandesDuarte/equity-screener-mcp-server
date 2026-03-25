# src/services/yahoo_finance_service.py

import csv
from datetime import datetime, timezone
from pathlib import Path

from src.scraper.engine import ScraperEngine
from src.storage.database import get_connection
from src.storage.repository import StockRepository


class YahooFinanceService:
    """Orchestrates scraping, CSV export, and DuckDB persistence."""

    def __init__(self, engine: ScraperEngine) -> None:
        self.engine: ScraperEngine = engine
        # Expose driver so main.py can call driver.quit() for cleanup
        self.driver = engine.driver

    def fetch_data(self, region: str) -> list[dict[str, str]]:
        """Scrape a region, persist to CSV + DuckDB, and return the rows."""
        data: list[dict[str, str]] = self.engine.scrape(region)

        if data:
            file_saved = self._export_to_csv(data, region)
            print(f"✅ Data saved to: {file_saved}")

            scraped_at = datetime.now(tz=timezone.utc)
            conn = get_connection()
            repo = StockRepository(conn)
            repo.insert_batch(region, data, scraped_at)
            repo.upsert_region_metadata(region, scraped_at)
            conn.close()
            print(f"🗄️  Data persisted to DuckDB ({len(data)} rows).")

        return data

    def _export_to_csv(self, data: list[dict[str, str]], region: str) -> str:
        output_dir = Path("data/outputs")
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{region.lower().replace(' ', '_')}_{timestamp}.csv"
        file_path = output_dir / filename
        with open(file_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["symbol", "name", "price"])
            writer.writeheader()
            writer.writerows(data)
        return str(file_path)
