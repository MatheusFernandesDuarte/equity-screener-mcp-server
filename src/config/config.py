# src/config/config.py


import os

from selenium.webdriver.chrome.options import Options


class AppConfig:
    """Centralized configuration for the application."""

    BASE_URL: str = "https://finance.yahoo.com/research-hub/screener/equity/"
    CHROME_BIN: str | None = os.getenv("CHROME_BIN")
    CHROMEDRIVER_PATH: str = os.getenv("CHROMEDRIVER_BIN", "/usr/bin/chromedriver")

    @classmethod
    def get_selenium_options(cls) -> Options:
        """Return standardized Chrome options for both local and Docker environments."""
        options = Options()

        # Binary location for Docker
        if cls.CHROME_BIN:
            options.binary_location = cls.CHROME_BIN

        # Headless and Sandbox settings
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")

        # Anti-bot detection measures
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        return options
