# src/app/main.py


from src.app.factories import create_yahoo_service
from src.services.yahoo_finance_service import YahooFinanceService


def run(region: str) -> None:
    """
    Orchestrate the crawling process for a specific geographic region.

    Ensures the service is created, data is fetched, and browser resources
    are always released.
    """
    print(f"🚀 Starting Crawler for region: {region}...")

    service: YahooFinanceService | None = None

    try:
        service = create_yahoo_service()

        data: list[dict[str, str]] = service.fetch_data(region)

        if not data:
            print(f"⚠️ No data found or processed for region: {region}")
            return

        print(f"✅ Success! {len(data)} records processed and saved.")

    except Exception as e:
        print(f"❌ Critical error during execution: {e}")

    finally:
        if service and hasattr(service, "driver"):
            service.driver.quit()
            print("🌐 Browser session closed safely.")
