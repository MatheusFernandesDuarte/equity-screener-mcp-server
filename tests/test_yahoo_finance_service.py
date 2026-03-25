# tests/test_yahoo_finance_service.py

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup

from src.services import yahoo_finance_service
from src.services.yahoo_finance_service import YahooFinanceService
from src.scraper.engine import ScraperEngine


@pytest.fixture
def mock_driver() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_engine(mock_driver: MagicMock) -> ScraperEngine:
    engine = ScraperEngine(mock_driver)
    engine.wait = MagicMock()
    return engine


@pytest.fixture
def yahoo_service(mock_engine: ScraperEngine) -> YahooFinanceService:
    return YahooFinanceService(engine=mock_engine)


def test_symbol_extraction_logic() -> None:
    """BS4 correctly extracts a symbol from a span.symbol element."""
    html_snippet: str = """
    <table>
        <tbody>
            <tr>
                <td>1</td>
                <td><span class="symbol">NVDA.BA</span></td>
                <td>NVIDIA Corporation</td>
                <td>Chart</td>
                <td>165,300.00</td>
            </tr>
        </tbody>
    </table>
    """
    soup = BeautifulSoup(html_snippet, "html.parser")
    cols = soup.find_all("td")
    raw_symbol_text = cols[1].get_text(strip=True)
    symbol = raw_symbol_text.split("\n")[-1].strip()
    assert symbol == "NVDA.BA"


def test_extract_table_with_mock_html(mock_engine: ScraperEngine, mock_driver: MagicMock) -> None:
    """ScraperEngine._extract_table parses page_source via BS4."""
    mock_html: str = """
    <table>
        <tbody>
            <tr>
                <td>1</td>
                <td><a aria-label="Apple Inc."><span class="symbol">AAPL.BA</span></a></td>
                <td>Apple Inc.</td>
                <td>Chart</td>
                <td>150.00</td>
            </tr>
        </tbody>
    </table>
    """
    mock_driver.page_source = mock_html
    mock_engine.wait.until = MagicMock(return_value=True)

    results = mock_engine._extract_table()

    assert len(results) == 1
    assert results[0]["symbol"] == "AAPL.BA"
    assert results[0]["name"] == "Apple Inc."
    assert results[0]["price"] == "150.00"


def test_export_to_csv(yahoo_service: YahooFinanceService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """YahooFinanceService._export_to_csv creates a valid CSV file."""
    test_data = [{"symbol": "TEST.BA", "name": "Test Company", "price": "100.00"}]
    mock_output_dir = tmp_path / "data" / "outputs"

    monkeypatch.setattr(
        yahoo_finance_service,
        "Path",
        lambda *args: mock_output_dir if "data/outputs" in args else Path(*args),
    )

    file_saved_path = yahoo_service._export_to_csv(test_data, "Argentina")
    final_path = Path(file_saved_path)

    assert final_path.exists()
    content = final_path.read_text(encoding="utf-8")
    assert "symbol,name,price" in content
    assert "TEST.BA,Test Company,100.00" in content
