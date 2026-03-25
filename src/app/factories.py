# src/app/factories.py

from typing import Callable

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from src.config.config import AppConfig
from src.scraper.engine import ScraperEngine
from src.services.yahoo_finance_service import YahooFinanceService


def create_engine_factory() -> Callable[[], ScraperEngine]:
    """Return a callable that creates a fresh ScraperEngine on each call.

    Used by ScrapeManager so each background scrape gets its own WebDriver.
    """
    def factory() -> ScraperEngine:
        options = AppConfig.get_selenium_options()
        if AppConfig.CHROME_BIN:
            chrome_service = Service(executable_path=AppConfig.CHROMEDRIVER_PATH)
        else:
            chrome_service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=chrome_service, options=options)
        return ScraperEngine(driver)
    return factory


def create_yahoo_service() -> YahooFinanceService:
    """Build a configured YahooFinanceService backed by a headless Chrome engine."""
    engine = create_engine_factory()()
    return YahooFinanceService(engine)
