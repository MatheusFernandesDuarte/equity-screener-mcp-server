"""Tests for ScraperEngine.

All Selenium interactions are mocked — no live browser required.
"""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.scraper.engine import ScraperEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_driver(page_source: str = "") -> MagicMock:
    driver = MagicMock()
    type(driver).page_source = PropertyMock(return_value=page_source)
    return driver


def make_engine(page_source: str = "") -> ScraperEngine:
    driver = make_driver(page_source)
    engine = ScraperEngine(driver)
    engine.wait = MagicMock()
    return engine


SINGLE_ROW_HTML = """
<table>
  <tbody>
    <tr>
      <td></td>
      <td><a aria-label="Apple Inc."><span class="symbol">AAPL.BA</span></a></td>
      <td>Apple Inc.</td>
      <td></td>
      <td>150.00</td>
    </tr>
  </tbody>
</table>
"""

MULTI_ROW_HTML = """
<table>
  <tbody>
    <tr>
      <td></td>
      <td><a aria-label="Apple"><span class="symbol">AAPL.BA</span></a></td>
      <td>Apple Inc.</td>
      <td></td>
      <td>150.00</td>
    </tr>
    <tr>
      <td></td>
      <td><a aria-label="Microsoft"><span class="symbol">MSFT.BA</span></a></td>
      <td>Microsoft Corp.</td>
      <td></td>
      <td>320.50</td>
    </tr>
  </tbody>
</table>
"""

NO_SYMBOL_HTML = """
<table>
  <tbody>
    <tr>
      <td></td>
      <td><span>not an anchor</span></td>
      <td>Some Company</td>
      <td></td>
      <td>100.00</td>
    </tr>
  </tbody>
</table>
"""


# ---------------------------------------------------------------------------
# _parse_table (pure HTML parsing, no Selenium)
# ---------------------------------------------------------------------------

def test_parse_table_extracts_symbol_name_price():
    engine = make_engine(SINGLE_ROW_HTML)
    results = engine._parse_table(SINGLE_ROW_HTML)
    assert len(results) == 1
    assert results[0]["symbol"] == "AAPL.BA"
    assert results[0]["name"] == "Apple Inc."
    assert results[0]["price"] == "150.00"


def test_parse_table_extracts_multiple_rows():
    engine = make_engine(MULTI_ROW_HTML)
    results = engine._parse_table(MULTI_ROW_HTML)
    assert len(results) == 2
    symbols = {r["symbol"] for r in results}
    assert symbols == {"AAPL.BA", "MSFT.BA"}


def test_parse_table_skips_rows_without_anchor():
    engine = make_engine(NO_SYMBOL_HTML)
    results = engine._parse_table(NO_SYMBOL_HTML)
    assert results == []


def test_parse_table_returns_empty_on_empty_html():
    engine = make_engine("<html></html>")
    results = engine._parse_table("<html></html>")
    assert results == []


def test_parse_table_uses_aria_label_as_name_fallback():
    html = """
    <table><tbody><tr>
      <td></td>
      <td><a aria-label="Fallback Name"><span class="symbol">SYM</span></a></td>
      <td>--</td>
      <td></td>
      <td>99.00</td>
    </tr></tbody></table>
    """
    engine = make_engine(html)
    results = engine._parse_table(html)
    assert results[0]["name"] == "Fallback Name"


def test_parse_table_symbol_not_duplicated():
    """Regression: symbol must not include repeated first char."""
    html = """
    <table><tbody><tr>
      <td></td>
      <td><a><span class="symbol">NVDA.BA</span></a></td>
      <td>Nvidia</td>
      <td></td>
      <td>500.00</td>
    </tr></tbody></table>
    """
    engine = make_engine(html)
    results = engine._parse_table(html)
    assert results[0]["symbol"] == "NVDA.BA"


# ---------------------------------------------------------------------------
# _extract_table (calls Selenium wait then delegates to _parse_table)
# ---------------------------------------------------------------------------

def test_extract_table_returns_parsed_rows():
    engine = make_engine(SINGLE_ROW_HTML)
    engine.wait.until = MagicMock(return_value=True)

    with patch("src.scraper.engine.time.sleep"):
        results = engine._extract_table()

    assert len(results) == 1
    assert results[0]["symbol"] == "AAPL.BA"


def test_extract_table_returns_empty_on_wait_timeout():
    engine = make_engine("<html></html>")
    engine.wait.until = MagicMock(side_effect=Exception("timeout"))

    results = engine._extract_table()
    assert results == []


# ---------------------------------------------------------------------------
# _select_and_cleanup_region
# ---------------------------------------------------------------------------

def test_select_region_returns_early_for_united_states():
    engine = make_engine()
    # Should not call wait.until at all for United States
    engine._select_and_cleanup_region("United States")
    engine.wait.until.assert_not_called()


# ---------------------------------------------------------------------------
# _extract_all_pages (pagination)
# ---------------------------------------------------------------------------

def test_extract_all_pages_stops_when_next_disabled():
    engine = make_engine(SINGLE_ROW_HTML)
    engine.wait.until = MagicMock(return_value=True)

    next_btn = MagicMock()
    next_btn.get_attribute.return_value = "true"   # disabled=true
    engine.driver.find_element = MagicMock(return_value=next_btn)

    with patch("src.scraper.engine.time.sleep"):
        results = engine._extract_all_pages()

    assert len(results) == 1


def test_extract_all_pages_stops_when_next_not_found():
    engine = make_engine(SINGLE_ROW_HTML)
    engine.wait.until = MagicMock(return_value=True)
    engine.driver.find_element = MagicMock(side_effect=Exception("not found"))

    with patch("src.scraper.engine.time.sleep"):
        results = engine._extract_all_pages()

    assert len(results) == 1


# ---------------------------------------------------------------------------
# scrape (integration of all steps)
# ---------------------------------------------------------------------------

def test_scrape_returns_list_of_dicts():
    engine = make_engine(SINGLE_ROW_HTML)

    with patch.object(engine, "_select_and_cleanup_region"), \
         patch.object(engine, "_set_rows_to_100"), \
         patch.object(engine, "_extract_all_pages", return_value=[
             {"symbol": "AAPL.BA", "name": "Apple", "price": "150.00"}
         ]):
        results = engine.scrape("Argentina")

    assert len(results) == 1
    assert results[0]["symbol"] == "AAPL.BA"


def test_scrape_navigates_to_base_url():
    engine = make_engine()

    with patch.object(engine, "_select_and_cleanup_region"), \
         patch.object(engine, "_set_rows_to_100"), \
         patch.object(engine, "_extract_all_pages", return_value=[]):
        engine.scrape("Belgium")

    engine.driver.get.assert_called_once_with(ScraperEngine.BASE_URL)
