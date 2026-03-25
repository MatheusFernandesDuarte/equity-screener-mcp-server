# Extending Providers

## Adding a new AI provider

### 1. Implement the interface

Create `src/ai/your_provider.py`:

```python
import os
from src.ai.base import AIProvider


class YourProvider(AIProvider):

    def __init__(self) -> None:
        # Read your API key — factory handles missing key before calling __init__
        api_key = os.environ["YOUR_PROVIDER_API_KEY"]
        # initialize your client here

    def summarize(self, data: list[dict]) -> str:
        # data is a list of {symbol, name, price, scraped_at} dicts
        # max 50 rows, latest snapshot only (pre-sliced by MarketService)
        ...

    def detect_anomalies(self, data: list[dict]) -> list[dict]:
        # return list of {symbol, reason, severity}
        ...

    def analyze_trends(self, data: list[dict]) -> dict:
        # return {direction, notable_movers, confidence}
        ...
```

### 2. Register in the factory

Edit `src/ai/factory.py`, add your provider to `_PROVIDERS`:

```python
_PROVIDERS = {
    ...
    "your_provider": ("src.ai.your_provider", "YourProvider", "YOUR_PROVIDER_API_KEY"),
}
```

### 3. Write tests

Add to `tests/test_ai_providers.py`:

```python
def test_your_provider_summarize_calls_api():
    from src.ai.your_provider import YourProvider

    mock_client = MagicMock()
    # set up mock response ...

    with patch.dict(os.environ, {"YOUR_PROVIDER_API_KEY": "test"}), \
         patch("src.ai.your_provider.YourSDK", return_value=mock_client):
        provider = YourProvider()
        result = provider.summarize(SMALL_DATA)

    assert isinstance(result, str)
```

### 4. Use it

```bash
AI_PROVIDER=your_provider YOUR_PROVIDER_API_KEY=... python mcp_server.py
```

---

## Adding a new data source

Today the only scraper is Yahoo Finance. To add a second source (e.g. a different exchange or API):

### 1. Implement a new engine

Create `src/scraper/your_source_engine.py` with a `scrape(region: str) -> list[dict]` method returning `[{symbol, name, price}]`.

### 2. Add a factory function

In `src/app/factories.py`, add a `create_your_source_engine_factory()` that returns a `Callable[[], YourSourceEngine]`.

### 3. Wire into ScrapeManager

`ScrapeManager` accepts any `engine_factory: Callable[[], Any]` as long as the returned object has a `.scrape(region)` method and a `.driver` attribute (or handle cleanup differently).

### 4. Repository is source-agnostic

`StockRepository.insert_batch()` only cares about `{symbol, name, price}` — it works with any source.

---

## Freshness and TTL

`MarketService._compute_ttl(access_count)` controls how long cached data is considered fresh:

| Access count | TTL |
|---|---|
| 0–10 | 4 hours (14400s) |
| 11–50 | 2 hours (7200s) |
| 50+ | 1 hour (3600s) |

To override, subclass `MarketService` and override `_compute_ttl`.
