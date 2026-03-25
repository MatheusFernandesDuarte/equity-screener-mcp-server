# src/app/factories.py

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from src.config.config import AppConfig
from src.scraper.engine import ScraperEngine
from src.services.yahoo_finance_service import YahooFinanceService


def create_yahoo_service() -> YahooFinanceService:
    """Build a configured YahooFinanceService backed by a headless Chrome engine."""
    options = AppConfig.get_selenium_options()

    if AppConfig.CHROME_BIN:
        service = Service(executable_path=AppConfig.CHROMEDRIVER_PATH)
    else:
        service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=options)
    engine = ScraperEngine(driver)
    return YahooFinanceService(engine)
