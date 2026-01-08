# src/app/main.py

from src.app.factories import create_yahoo_service
from src.services.yahoo_finance_service import YahooFinanceService


def run(region: str) -> None:
    """Orchestrate the crawling process for a specific geographic region."""
    print(f"🚀 Starting Crawler for region: {region}...")
    service: YahooFinanceService = create_yahoo_service()

    try:
        data: list[dict[str, str]] = service.fetch_data(region)

        if not data:
            print(f"⚠️ No data found for region: {region}")
            return

        print(f"✅ Success! {len(data)} records processed.")

    except Exception as e:
        print(f"❌ Critical error during execution: {e}")

    finally:
        service.driver.quit()
