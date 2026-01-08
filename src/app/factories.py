# src/app/factories.py


from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from src.config.config import AppConfig
from src.services.yahoo_finance_service import YahooFinanceService


def create_yahoo_service() -> YahooFinanceService:
    """Create and configure a YahooFinanceService instance with a Chrome WebDriver."""
    options: webdriver.ChromeOptions = AppConfig.get_selenium_options()
    driver: webdriver.Chrome = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return YahooFinanceService(driver)
