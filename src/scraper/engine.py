"""ScraperEngine — the only module in the codebase that touches Selenium.

All browser interaction, region selection, pagination, and HTML parsing
lives here. Nothing outside this module may import or instantiate a WebDriver.
"""

import time

from bs4 import BeautifulSoup, Tag
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class ScraperEngine:
    """Drives a headless Chrome session to scrape Yahoo Finance equity data."""

    BASE_URL: str = "https://finance.yahoo.com/research-hub/screener/equity/"

    def __init__(self, driver: WebDriver) -> None:
        self.driver: WebDriver = driver
        self.wait: WebDriverWait = WebDriverWait(driver, 15)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape(self, region: str) -> list[dict[str, str]]:
        """Navigate to the screener, apply region filter, and return all rows."""
        self.driver.get(self.BASE_URL)
        self._select_and_cleanup_region(region)
        self._set_rows_to_100()
        return self._extract_all_pages()

    # ------------------------------------------------------------------
    # Browser interaction
    # ------------------------------------------------------------------

    def _select_and_cleanup_region(self, target_region: str) -> None:
        """Select the target region and deselect all others."""
        if target_region == "United States":
            return

        region_btn: WebElement = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-ylk*='slk:Region']"))
        )
        region_btn.click()

        options_container: WebElement = self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.options"))
        )
        labels: list[WebElement] = options_container.find_elements(By.TAG_NAME, "label")

        target_checkbox: WebElement | None = None

        for label in labels:
            name: str = label.find_element(By.TAG_NAME, "span").text.strip()
            checkbox: WebElement = label.find_element(By.TAG_NAME, "input")
            if name.lower() == target_region.lower():
                target_checkbox = checkbox
                break

        if not target_checkbox:
            available: list[str] = [
                label.find_element(By.TAG_NAME, "span").text for label in labels
            ]
            raise ValueError(f"Region '{target_region}' not found. Available: {available}")

        if not target_checkbox.is_selected():
            self.driver.execute_script("arguments[0].click()", target_checkbox)
            time.sleep(0.3)

        for label in labels:
            name = label.find_element(By.TAG_NAME, "span").text.strip()
            checkbox = label.find_element(By.TAG_NAME, "input")
            if name.lower() != target_region.lower() and checkbox.is_selected():
                self.driver.execute_script("arguments[0].click()", checkbox)
                time.sleep(0.2)

        apply_btn: WebElement = self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label='Apply']"))
        )
        self.driver.execute_script(
            """
            arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
            arguments[0].dispatchEvent(new Event('blur',   { bubbles: true }));
            """,
            apply_btn,
        )
        self.wait.until(lambda d: not apply_btn.get_attribute("disabled"))
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", apply_btn
        )
        time.sleep(0.3)
        self.driver.execute_script("arguments[0].click()", apply_btn)
        time.sleep(2)

    def _set_rows_to_100(self) -> None:
        """Set the rows-per-page dropdown to 100 if it is not already."""
        try:
            dropdown_btn: WebElement = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.select-dropdown button"))
            )
            if "100" in dropdown_btn.text.strip():
                return
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", dropdown_btn
            )
            time.sleep(0.5)
            self.driver.execute_script("arguments[0].click();", dropdown_btn)
            option_100: WebElement = self.wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "div[role='option'][data-value='100']")
                )
            )
            self.driver.execute_script("arguments[0].click();", option_100)
            time.sleep(3)
        except Exception:
            pass

    def _extract_all_pages(self) -> list[dict[str, str]]:
        """Iterate through all result pages and aggregate rows."""
        all_data: list[dict[str, str]] = []
        while True:
            page_data = self._extract_table()
            if not page_data:
                break
            all_data.extend(page_data)
            try:
                next_btn: WebElement = self.driver.find_element(
                    By.CSS_SELECTOR, "button[data-testid='next-page-button']"
                )
                disabled = next_btn.get_attribute("disabled") is not None or "disabled" in (
                    next_btn.get_attribute("class") or ""
                )
                if disabled:
                    break
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", next_btn
                )
                time.sleep(0.5)
                self.driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(4)
            except Exception:
                break
        return all_data

    def _extract_table(self) -> list[dict[str, str]]:
        """Wait for the table to render then parse the current page source."""
        try:
            self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table tbody tr"))
            )
            time.sleep(2)
            return self._parse_table(self.driver.page_source)
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Pure HTML parsing (no Selenium dependency — easily unit-tested)
    # ------------------------------------------------------------------

    def _parse_table(self, html: str) -> list[dict[str, str]]:
        """Extract symbol, name, and price from a Yahoo Finance equity table."""
        soup = BeautifulSoup(html, "html.parser")
        rows: list[Tag] = soup.select("table tbody tr")
        results: list[dict[str, str]] = []

        for row in rows:
            try:
                cols: list[Tag] = row.find_all("td")
                if len(cols) < 5:
                    continue

                anchor = cols[1].find("a")
                if not anchor:
                    continue

                symbol_span = anchor.find("span", class_="symbol")
                symbol: str = (
                    symbol_span.get_text(strip=True)
                    if symbol_span
                    else anchor.get_text(strip=True)
                )

                name: str = cols[2].get_text(strip=True)
                if not name or name == "--":
                    name = anchor.get("aria-label", "") or ""

                price: str = cols[4].get_text(strip=True)

                if symbol and price:
                    results.append({"symbol": symbol, "name": name, "price": price})
            except Exception:
                continue

        return results
