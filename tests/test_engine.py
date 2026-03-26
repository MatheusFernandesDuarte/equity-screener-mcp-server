"""Tests for ScraperEngine (HTTP-based).

All HTTP calls are mocked — no network required.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.scraper.engine import ScraperEngine, _REGION_CODES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_engine() -> ScraperEngine:
    session = MagicMock()
    return ScraperEngine(session)


def mock_response(json_data=None, text="", status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    return resp


SAMPLE_SCREENER_RESPONSE = {
    "finance": {
        "result": [{
            "quotes": [
                {
                    "symbol": "AAPL.BA",
                    "longName": "Apple Inc.",
                    "regularMarketPrice": 150.0,
                    "regularMarketChangePercent": 1.25,
                },
                {
                    "symbol": "MSFT.BA",
                    "longName": "Microsoft Corp.",
                    "regularMarketPrice": 320.5,
                    "regularMarketChangePercent": -0.75,
                },
            ]
        }]
    }
}


# ---------------------------------------------------------------------------
# _to_region_code
# ---------------------------------------------------------------------------

def test_to_region_code_known_region():
    assert ScraperEngine._to_region_code("Argentina") == "ar"
    assert ScraperEngine._to_region_code("brazil") == "br"
    assert ScraperEngine._to_region_code("United States") == "us"
    assert ScraperEngine._to_region_code("United Kingdom") == "gb"


def test_to_region_code_case_insensitive():
    assert ScraperEngine._to_region_code("ARGENTINA") == "ar"
    assert ScraperEngine._to_region_code("  Brazil  ") == "br"


def test_to_region_code_unknown_falls_back_to_first_two_chars():
    code = ScraperEngine._to_region_code("Wakanda")
    assert code == "wa"


def test_to_region_code_unknown_too_short_raises():
    with pytest.raises(ValueError, match="Unknown region"):
        ScraperEngine._to_region_code("X")


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------

def test_parse_response_extracts_symbol_name_price_change_pct():
    engine = make_engine()
    results = engine._parse_response(SAMPLE_SCREENER_RESPONSE)
    assert len(results) == 2
    assert results[0]["symbol"] == "AAPL.BA"
    assert results[0]["name"] == "Apple Inc."
    assert results[0]["price"] == "150.0"
    assert results[0]["change_pct"] == "1.25"


def test_parse_response_negative_change_pct():
    engine = make_engine()
    results = engine._parse_response(SAMPLE_SCREENER_RESPONSE)
    assert results[1]["change_pct"] == "-0.75"


def test_parse_response_missing_change_pct_returns_empty_string():
    engine = make_engine()
    data = {"finance": {"result": [{"quotes": [
        {"symbol": "X", "longName": "X Corp", "regularMarketPrice": 10.0}
    ]}]}}
    results = engine._parse_response(data)
    assert results[0]["change_pct"] == ""


def test_parse_response_skips_rows_without_symbol():
    engine = make_engine()
    data = {"finance": {"result": [{"quotes": [
        {"longName": "No Symbol", "regularMarketPrice": 10.0}
    ]}]}}
    assert engine._parse_response(data) == []


def test_parse_response_skips_rows_without_price():
    engine = make_engine()
    data = {"finance": {"result": [{"quotes": [
        {"symbol": "SYM", "longName": "Some Co"}
    ]}]}}
    assert engine._parse_response(data) == []


def test_parse_response_returns_empty_on_malformed_response():
    engine = make_engine()
    assert engine._parse_response({}) == []
    assert engine._parse_response({"finance": {}}) == []
    assert engine._parse_response({"finance": {"result": []}}) == []


def test_parse_response_uses_shortname_fallback():
    engine = make_engine()
    data = {"finance": {"result": [{"quotes": [
        {"symbol": "SYM", "shortName": "Short Co", "regularMarketPrice": 5.0}
    ]}]}}
    results = engine._parse_response(data)
    assert results[0]["name"] == "Short Co"


# ---------------------------------------------------------------------------
# _authenticate
# ---------------------------------------------------------------------------

def test_authenticate_sets_crumb():
    engine = make_engine()
    engine._session.get.side_effect = [
        mock_response(),                  # consent GET
        mock_response(text="test-crumb"), # crumb GET
    ]
    engine._authenticate()
    assert engine._crumb == "test-crumb"


def test_authenticate_raises_if_crumb_empty():
    engine = make_engine()
    engine._session.get.side_effect = [
        mock_response(),
        mock_response(text="  "),
    ]
    with pytest.raises(RuntimeError, match="crumb"):
        engine._authenticate()


# ---------------------------------------------------------------------------
# _fetch_page
# ---------------------------------------------------------------------------

def test_fetch_page_posts_to_screener_with_crumb():
    engine = make_engine()
    engine._crumb = "my-crumb"
    engine._session.post.return_value = mock_response(SAMPLE_SCREENER_RESPONSE)

    results = engine._fetch_page("ar", 0)

    assert len(results) == 2
    call_kwargs = engine._session.post.call_args
    assert call_kwargs.kwargs["params"]["crumb"] == "my-crumb"
    assert call_kwargs.kwargs["json"]["query"]["operands"][0]["operands"] == ["region", "ar"]


def test_fetch_page_passes_offset():
    engine = make_engine()
    engine._crumb = "x"
    engine._session.post.return_value = mock_response({"finance": {"result": [{"quotes": []}]}})

    engine._fetch_page("br", 250)

    payload = engine._session.post.call_args.kwargs["json"]
    assert payload["offset"] == 250


# ---------------------------------------------------------------------------
# _fetch_all_pages (pagination)
# ---------------------------------------------------------------------------

def test_fetch_all_pages_stops_when_batch_smaller_than_page_size():
    engine = make_engine()
    engine._crumb = "x"
    engine._session.post.return_value = mock_response(SAMPLE_SCREENER_RESPONSE)

    results = engine._fetch_all_pages("ar")

    # 2 quotes < PAGE_SIZE=250, so only one page fetched
    assert engine._session.post.call_count == 1
    assert len(results) == 2


def test_fetch_all_pages_paginates_until_short_page():
    engine = make_engine()
    engine._crumb = "x"

    # First call returns exactly PAGE_SIZE quotes, second returns 1
    full_page = [
        {"symbol": f"S{i}", "longName": f"Co{i}", "regularMarketPrice": float(i)}
        for i in range(250)
    ]
    last_page = [{"symbol": "LAST", "longName": "Last", "regularMarketPrice": 1.0}]

    def side_effect(*args, **kwargs):
        offset = kwargs["json"]["offset"]
        quotes = full_page if offset == 0 else last_page
        return mock_response({"finance": {"result": [{"quotes": quotes}]}})

    engine._session.post.side_effect = side_effect
    results = engine._fetch_all_pages("br")

    assert engine._session.post.call_count == 2
    assert len(results) == 251


# ---------------------------------------------------------------------------
# scrape (full flow)
# ---------------------------------------------------------------------------

def test_scrape_authenticates_then_fetches():
    engine = make_engine()
    engine._session.get.side_effect = [
        mock_response(),
        mock_response(text="crumb-123"),
    ]
    engine._session.post.return_value = mock_response(SAMPLE_SCREENER_RESPONSE)

    results = engine.scrape("Argentina")

    assert engine._crumb == "crumb-123"
    assert len(results) == 2
    assert results[0]["symbol"] == "AAPL.BA"


def test_scrape_reuses_crumb_on_second_call():
    engine = make_engine()
    engine._crumb = "already-set"
    engine._session.post.return_value = mock_response(SAMPLE_SCREENER_RESPONSE)

    engine.scrape("Brazil")

    # No GET calls since crumb already set
    engine._session.get.assert_not_called()
