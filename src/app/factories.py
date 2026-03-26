# src/app/factories.py

from typing import Callable

import requests

from src.scraper.engine import _HEADERS, ScraperEngine
from src.services.yahoo_finance_service import YahooFinanceService


def create_engine_factory() -> Callable[[], ScraperEngine]:
    """Return a callable that creates a fresh ScraperEngine on each call.

    Each background scrape gets its own requests.Session so sessions
    don't share cookies or crumb state across concurrent workers.
    """

    def factory() -> ScraperEngine:
        session = requests.Session()
        session.headers.update(_HEADERS)
        return ScraperEngine(session)

    return factory


def create_yahoo_service() -> YahooFinanceService:
    """Build a configured YahooFinanceService backed by an HTTP scraper."""
    engine = create_engine_factory()()
    return YahooFinanceService(engine)
