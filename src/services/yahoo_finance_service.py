# src/services/yahoo_finance_service.py


import csv
import time
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.storage.database import get_connection
from src.storage.repository import StockRepository


class YahooFinanceService:
    """Service responsible for crawling Yahoo Finance equity data."""

    def __init__(self, driver: WebDriver):
        """Initialize the service with a WebDriver instance."""
        self.driver: WebDriver = driver
        self.wait: WebDriverWait = WebDriverWait(self.driver, 15)

    def _select_and_cleanup_region(self, target_region: str) -> None:
        """Handle the selection of the target region and deselect previous filters."""
        if target_region == "United States":
            return

        region_btn: WebElement = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-ylk*='slk:Region']")))
        region_btn.click()

        options_container: WebElement = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.options")))
        labels: list[WebElement] = options_container.find_elements(By.TAG_NAME, "label")

        target_checkbox: WebElement | None = None

        for label in labels:
            name: str = label.find_element(By.TAG_NAME, "span").text.strip()
            checkbox: WebElement = label.find_element(By.TAG_NAME, "input")

            if name.lower() == target_region.lower():
                target_checkbox = checkbox
                break

        if not target_checkbox:
            available: list[str] = [label.find_element(By.TAG_NAME, "span").text for label in labels]
            raise ValueError(f"Region '{target_region}' not found. Available: {available}")
        if not target_checkbox.is_selected():
            self.driver.execute_script("arguments[0].click()", target_checkbox)
            time.sleep(0.3)

        for label in labels:
            name: str = label.find_element(By.TAG_NAME, "span").text.strip()
            checkbox: WebElement = label.find_element(By.TAG_NAME, "input")
            if name.lower() != target_region.lower() and checkbox.is_selected():
                self.driver.execute_script("arguments[0].click()", checkbox)
                time.sleep(0.2)

        apply_btn: WebElement = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label='Apply']")))

        self.driver.execute_script(
            """
            arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
            arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));
            """,
            apply_btn,
        )

        self.wait.until(lambda d: not apply_btn.get_attribute("disabled"))
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", apply_btn)
        time.sleep(0.3)
        self.driver.execute_script("arguments[0].click()", apply_btn)
        time.sleep(2)

    def _extract_table(self) -> list[dict[str, str]]:
        """Extract symbol, name, and price data using BeautifulSoup for parsing."""
        try:
            self.wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table tbody tr")))
            time.sleep(2)

            soup: BeautifulSoup = BeautifulSoup(self.driver.page_source, "html.parser")

            rows: list[Tag] = soup.select("table tbody tr")
            results: list[dict[str, str]] = []

            for row in rows:
                try:
                    cols: list[Tag] = row.find_all("td")
                    if len(cols) >= 5:
                        anchor = cols[1].find("a")
                        if anchor:
                            raw_symbol = anchor.get_text(strip=True)
                            symbol_span = anchor.find("span", class_="symbol")
                            if symbol_span:
                                symbol = symbol_span.get_text(strip=True)
                            else:
                                symbol = raw_symbol
                        else:
                            continue

                        name: str = cols[2].get_text(strip=True)
                        if name == "--" or not name:
                            name = anchor.get("aria-label", "") if anchor else ""

                        price: str = cols[4].get_text(strip=True)

                        if symbol and price:
                            results.append({"symbol": symbol, "name": name, "price": price})
                except Exception:
                    continue

            return results

        except Exception:
            return []

    def _set_rows_to_100(self) -> None:
        """Configure the table view to display 100 rows per page."""
        try:
            dropdown_btn: WebElement = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div.select-dropdown button")))

            current_value: str = dropdown_btn.text.strip()
            if "100" in current_value:
                return

            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown_btn)
            time.sleep(0.5)
            self.driver.execute_script("arguments[0].click();", dropdown_btn)

            option_100: WebElement = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div[role='option'][data-value='100']")))

            self.driver.execute_script("arguments[0].click();", option_100)
            time.sleep(3)

        except Exception:
            pass

    def _extract_all_pages(self) -> list[dict[str, str]]:
        """Iterate through all available result pages and aggregate data."""
        all_data: list[dict[str, str]] = []
        while True:
            page_data: list[dict[str, str]] = self._extract_table()
            if not page_data:
                break

            all_data.extend(page_data)

            try:
                next_btn: WebElement = self.driver.find_element(By.CSS_SELECTOR, "button[data-testid='next-page-button']")
                is_disabled: bool = next_btn.get_attribute("disabled") is not None or "disabled" in (next_btn.get_attribute("class") or "")

                if is_disabled:
                    break

                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
                time.sleep(0.5)
                self.driver.execute_script("arguments[0].click();", next_btn)

                time.sleep(4)
            except Exception:
                break
        return all_data

    def _export_to_csv(self, data: list[dict[str, str]], region: str) -> str:
        """Create output directory and export data to a timestamped CSV file."""
        output_dir: Path = Path("data/outputs")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create filename with timestamp: region_YYYYMMDD_HHMMSS.csv
        timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename: str = f"{region.lower().replace(' ', '_')}_{timestamp}.csv"
        file_path: Path = output_dir / filename

        with open(file_path, mode="w", newline="", encoding="utf-8") as f:
            writer: csv.DictWriter = csv.DictWriter(f, fieldnames=["symbol", "name", "price"])
            writer.writeheader()
            writer.writerows(data)

        return str(file_path)

    def fetch_data(self, region: str) -> list[dict[str, str]]:
        """Navigate to the screener, apply filters, and return aggregated stock data."""
        self.driver.get("https://finance.yahoo.com/research-hub/screener/equity/")

        self._select_and_cleanup_region(region)
        self._set_rows_to_100()

        data: list[dict[str, str]] = self._extract_all_pages()

        if data:
            file_saved: str = self._export_to_csv(data, region)
            print(f"✅ Data saved to: {file_saved}")

            scraped_at: datetime = datetime.now(tz=timezone.utc)
            conn = get_connection()
            repo = StockRepository(conn)
            repo.insert_batch(region, data, scraped_at)
            repo.upsert_region_metadata(region, scraped_at)
            conn.close()
            print(f"🗄️  Data persisted to DuckDB ({len(data)} rows).")

        return data
