# tests/test_yahoo_finance_service.py

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from src.services import yahoo_finance_service
from src.services.yahoo_finance_service import YahooFinanceService
from src.scraper.engine import ScraperEngine


@pytest.fixture
def mock_engine() -> ScraperEngine:
    session = MagicMock(spec=requests.Session)
    engine = ScraperEngine(session)
    engine._crumb = "test-crumb"
    return engine


@pytest.fixture
def yahoo_service(mock_engine: ScraperEngine) -> YahooFinanceService:
    return YahooFinanceService(engine=mock_engine)


def test_export_to_csv(yahoo_service: YahooFinanceService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """YahooFinanceService._export_to_csv creates a valid CSV file."""
    test_data = [{"symbol": "TEST.BA", "name": "Test Company", "price": "100.00", "change_pct": "1.5"}]
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
    assert "symbol,name,price,change_pct" in content
    assert "TEST.BA,Test Company,100.00,1.5" in content
