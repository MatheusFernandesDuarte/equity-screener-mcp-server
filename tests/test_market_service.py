"""Tests for MarketService.

All dependencies (repository, scrape_manager) are mocked.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.services.market_service import Freshness, MarketService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def utc_now():
    return datetime.now(tz=timezone.utc)


def make_meta(last_scraped_at, ttl_seconds=3600, access_count=0):
    return {
        "region": "Argentina",
        "last_scraped_at": last_scraped_at.replace(tzinfo=None).isoformat(),
        "ttl_seconds": ttl_seconds,
        "access_count": access_count,
    }


SAMPLE_ROWS = [
    {"symbol": "AAPL.BA", "name": "Apple", "price": 150.0, "scraped_at": "2026-03-25T12:00:00"},
    {"symbol": "MSFT.BA", "name": "Microsoft", "price": 320.0, "scraped_at": "2026-03-25T12:00:00"},
]


@pytest.fixture
def repo():
    return MagicMock()


@pytest.fixture
def manager():
    return MagicMock()


@pytest.fixture
def service(repo, manager):
    return MarketService(repository=repo, scrape_manager=manager)


# ---------------------------------------------------------------------------
# Freshness computation
# ---------------------------------------------------------------------------


def test_freshness_is_fresh_within_ttl(service):
    meta = make_meta(utc_now() - timedelta(seconds=1800), ttl_seconds=3600)
    assert service._compute_freshness(meta) == Freshness.FRESH


def test_freshness_is_stale_between_ttl_and_2x_ttl(service):
    meta = make_meta(utc_now() - timedelta(seconds=5000), ttl_seconds=3600)
    assert service._compute_freshness(meta) == Freshness.STALE


def test_freshness_is_expired_beyond_2x_ttl(service):
    meta = make_meta(utc_now() - timedelta(seconds=8000), ttl_seconds=3600)
    assert service._compute_freshness(meta) == Freshness.EXPIRED


def test_freshness_is_expired_when_no_metadata(service):
    assert service._compute_freshness(None) == Freshness.EXPIRED


# ---------------------------------------------------------------------------
# Dynamic TTL
# ---------------------------------------------------------------------------


def test_compute_ttl_returns_14400_for_new_region(service):
    assert service._compute_ttl(0) == 14400


def test_compute_ttl_returns_7200_for_moderate_access(service):
    assert service._compute_ttl(15) == 7200


def test_compute_ttl_returns_3600_for_popular_region(service):
    assert service._compute_ttl(60) == 3600


# ---------------------------------------------------------------------------
# get_stocks_by_region — data + freshness
# ---------------------------------------------------------------------------


def test_get_stocks_returns_cached_data(service, repo):
    repo.get_latest_by_region.return_value = SAMPLE_ROWS
    repo.get_region_metadata.return_value = make_meta(utc_now() - timedelta(seconds=100))

    response = service.get_stocks_by_region("Argentina")

    assert response["data"] == SAMPLE_ROWS
    assert response["region"] == "Argentina"


def test_get_stocks_returns_freshness_state(service, repo):
    repo.get_latest_by_region.return_value = SAMPLE_ROWS
    repo.get_region_metadata.return_value = make_meta(utc_now() - timedelta(seconds=100))

    response = service.get_stocks_by_region("Argentina")
    assert response["freshness"] == Freshness.FRESH.value


def test_get_stocks_does_not_trigger_scrape_when_fresh(service, repo, manager):
    repo.get_latest_by_region.return_value = SAMPLE_ROWS
    repo.get_region_metadata.return_value = make_meta(utc_now() - timedelta(seconds=100))

    service.get_stocks_by_region("Argentina")
    manager.submit.assert_not_called()


def test_get_stocks_triggers_scrape_when_stale(service, repo, manager):
    repo.get_latest_by_region.return_value = SAMPLE_ROWS
    repo.get_region_metadata.return_value = make_meta(utc_now() - timedelta(seconds=5000))

    service.get_stocks_by_region("Argentina")
    manager.submit.assert_called_once_with("Argentina")


def test_get_stocks_triggers_scrape_when_expired(service, repo, manager):
    repo.get_latest_by_region.return_value = SAMPLE_ROWS
    repo.get_region_metadata.return_value = make_meta(utc_now() - timedelta(seconds=9000))

    service.get_stocks_by_region("Argentina")
    manager.submit.assert_called_once_with("Argentina")


def test_get_stocks_returns_data_immediately_even_when_stale(service, repo, manager):
    """Must never block on scraping — return cache and trigger refresh in background."""
    repo.get_latest_by_region.return_value = SAMPLE_ROWS
    repo.get_region_metadata.return_value = make_meta(utc_now() - timedelta(seconds=5000))

    response = service.get_stocks_by_region("Argentina")

    assert response["data"] == SAMPLE_ROWS  # stale data returned immediately
    manager.submit.assert_called_once()  # refresh triggered in background


def test_get_stocks_triggers_scrape_when_no_metadata(service, repo, manager):
    """Unknown region: no data, no metadata — must queue a scrape."""
    repo.get_latest_by_region.return_value = []
    repo.get_region_metadata.return_value = None

    service.get_stocks_by_region("Narnia")
    manager.submit.assert_called_once_with("Narnia")


def test_get_stocks_increments_access_count(service, repo):
    repo.get_latest_by_region.return_value = SAMPLE_ROWS
    repo.get_region_metadata.return_value = make_meta(utc_now() - timedelta(seconds=100))

    service.get_stocks_by_region("Argentina")
    repo.increment_access_count.assert_called_once_with("Argentina")


# ---------------------------------------------------------------------------
# get_top_movers
# ---------------------------------------------------------------------------


def test_get_top_movers_delegates_to_repo(service, repo):
    repo.get_top_movers.return_value = SAMPLE_ROWS[:1]
    result = service.get_top_movers("Argentina", n=5)
    repo.get_top_movers.assert_called_once_with("Argentina", 5, "price")
    assert result == SAMPLE_ROWS[:1]


# ---------------------------------------------------------------------------
# search_symbol
# ---------------------------------------------------------------------------


def test_search_symbol_delegates_to_repo(service, repo):
    repo.search_symbol.return_value = SAMPLE_ROWS
    result = service.search_symbol("AAPL")
    repo.search_symbol.assert_called_once_with("AAPL")
    assert result == SAMPLE_ROWS


# ---------------------------------------------------------------------------
# get_aggregated_for_ai
# ---------------------------------------------------------------------------


def test_get_aggregated_for_ai_limits_rows(service, repo):
    repo.get_aggregated_for_ai.return_value = SAMPLE_ROWS
    result = service.get_aggregated_for_ai("Argentina", limit=50)
    repo.get_aggregated_for_ai.assert_called_once_with("Argentina", 50)
    assert result == SAMPLE_ROWS
