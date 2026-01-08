# src/app/factories.py


from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from src.config.config import AppConfig
from src.services.yahoo_finance_service import YahooFinanceService


def create_yahoo_service() -> YahooFinanceService:
    """
    Factory to create a YahooFinanceService with pre-configured WebDriver.
    """
    options = AppConfig.get_selenium_options()

    if AppConfig.CHROME_BIN:
        service = Service(executable_path=AppConfig.CHROMEDRIVER_PATH)
    else:
        service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=options)
    return YahooFinanceService(driver)
