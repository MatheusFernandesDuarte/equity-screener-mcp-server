"""Tests for AI provider abstraction.

LocalProvider tests are pure (no mocks).
Cloud provider tests mock the underlying SDKs.
Factory tests mock environment variables.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from src.ai.base import AIProvider, MarketInsight
from src.ai.factory import get_provider
from src.ai.local import LocalProvider

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_DATA = [
    {"symbol": "A", "name": "A Co", "price": 10.0},
    {"symbol": "B", "name": "B Co", "price": 11.0},
    {"symbol": "C", "name": "C Co", "price": 12.0},
    {"symbol": "D", "name": "D Co", "price": 11.5},
    {"symbol": "E", "name": "E Co", "price": 10.5},
    {"symbol": "F", "name": "F Co", "price": 12.5},
    {"symbol": "G", "name": "G Co", "price": 11.0},
    {"symbol": "H", "name": "H Co", "price": 10.0},
    {"symbol": "OUTLIER", "name": "Way Up", "price": 100.0},
]

SMALL_DATA = [
    {"symbol": "X", "name": "X Co", "price": 100.0},
    {"symbol": "Y", "name": "Y Co", "price": 200.0},
]


# ---------------------------------------------------------------------------
# AIProvider ABC
# ---------------------------------------------------------------------------


def test_ai_provider_is_abstract():
    with pytest.raises(TypeError):
        AIProvider()


def test_market_insight_is_dataclass():
    insight = MarketInsight(
        summary="test",
        anomalies=[],
        trends={},
        provider="local",
        generated_at="2026-03-25T00:00:00",
    )
    assert insight.summary == "test"
    assert insight.provider == "local"


# ---------------------------------------------------------------------------
# LocalProvider — summarize
# ---------------------------------------------------------------------------


def test_local_summarize_contains_count():
    provider = LocalProvider()
    result = provider.summarize(SAMPLE_DATA)
    assert str(len(SAMPLE_DATA)) in result


def test_local_summarize_contains_avg():
    provider = LocalProvider()
    result = provider.summarize(SAMPLE_DATA)
    assert "avg" in result.lower() or any(char.isdigit() for char in result)


def test_local_summarize_handles_empty_data():
    provider = LocalProvider()
    result = provider.summarize([])
    assert isinstance(result, str)
    assert len(result) > 0


def test_local_summarize_handles_missing_price():
    provider = LocalProvider()
    data = [{"symbol": "A", "name": "A Co", "price": None}]
    result = provider.summarize(data)
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# LocalProvider — detect_anomalies
# ---------------------------------------------------------------------------


def test_local_detect_anomalies_flags_outlier():
    provider = LocalProvider()
    anomalies = provider.detect_anomalies(SAMPLE_DATA)
    symbols = [a["symbol"] for a in anomalies]
    assert "OUTLIER" in symbols


def test_local_detect_anomalies_returns_empty_for_small_dataset():
    provider = LocalProvider()
    anomalies = provider.detect_anomalies(SMALL_DATA)
    assert anomalies == []


def test_local_detect_anomalies_returns_list_of_dicts():
    provider = LocalProvider()
    anomalies = provider.detect_anomalies(SAMPLE_DATA)
    assert isinstance(anomalies, list)
    if anomalies:
        assert "symbol" in anomalies[0]
        assert "severity" in anomalies[0]
        assert "reason" in anomalies[0]


def test_local_detect_anomalies_handles_empty_data():
    provider = LocalProvider()
    assert provider.detect_anomalies([]) == []


# ---------------------------------------------------------------------------
# LocalProvider — analyze_trends
# ---------------------------------------------------------------------------


def test_local_analyze_trends_returns_required_keys():
    provider = LocalProvider()
    trends = provider.analyze_trends(SAMPLE_DATA)
    assert "direction" in trends
    assert "notable_movers" in trends
    assert "confidence" in trends


def test_local_analyze_trends_notable_movers_are_dicts():
    provider = LocalProvider()
    trends = provider.analyze_trends(SAMPLE_DATA)
    for mover in trends["notable_movers"]:
        assert "symbol" in mover
        assert "price" in mover


def test_local_analyze_trends_handles_empty_data():
    provider = LocalProvider()
    trends = provider.analyze_trends([])
    assert trends["direction"] == "unknown"


# ---------------------------------------------------------------------------
# LocalProvider — analyze (convenience method on base)
# ---------------------------------------------------------------------------


def test_analyze_returns_market_insight():
    provider = LocalProvider()
    insight = provider.analyze(SAMPLE_DATA)
    assert isinstance(insight, MarketInsight)
    assert insight.provider == "LocalProvider"
    assert insight.generated_at is not None


# ---------------------------------------------------------------------------
# Factory — provider resolution
# ---------------------------------------------------------------------------


def test_factory_returns_local_by_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AI_PROVIDER", None)
        provider = get_provider()
    assert isinstance(provider, LocalProvider)


def test_factory_returns_local_when_explicitly_set():
    with patch.dict(os.environ, {"AI_PROVIDER": "local"}):
        provider = get_provider()
    assert isinstance(provider, LocalProvider)


def test_factory_falls_back_to_local_when_api_key_missing():
    with patch.dict(os.environ, {"AI_PROVIDER": "claude"}, clear=False):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        provider = get_provider()
    assert isinstance(provider, LocalProvider)


def test_factory_falls_back_to_local_for_unknown_provider():
    with patch.dict(os.environ, {"AI_PROVIDER": "nonexistent"}):
        provider = get_provider()
    assert isinstance(provider, LocalProvider)


# ---------------------------------------------------------------------------
# Cloud providers — Claude (mocked SDK)
# ---------------------------------------------------------------------------


def test_claude_provider_summarize_calls_api():
    from src.ai.claude import ClaudeProvider

    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text="Market is up.")]

    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
        patch("src.ai.claude.anthropic.Anthropic", return_value=mock_client),
    ):
        provider = ClaudeProvider()
        result = provider.summarize(SMALL_DATA)

    assert result == "Market is up."
    mock_client.messages.create.assert_called_once()


def test_claude_provider_detect_anomalies_parses_json():
    from src.ai.claude import ClaudeProvider

    anomalies = [{"symbol": "X", "reason": "outlier", "severity": "high"}]
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text=json.dumps(anomalies))]

    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
        patch("src.ai.claude.anthropic.Anthropic", return_value=mock_client),
    ):
        provider = ClaudeProvider()
        result = provider.detect_anomalies(SMALL_DATA)

    assert result == anomalies


def test_claude_provider_detect_anomalies_returns_empty_on_bad_json():
    from src.ai.claude import ClaudeProvider

    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text="not json")]

    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
        patch("src.ai.claude.anthropic.Anthropic", return_value=mock_client),
    ):
        provider = ClaudeProvider()
        result = provider.detect_anomalies(SMALL_DATA)

    assert result == []


# ---------------------------------------------------------------------------
# Cloud providers — OpenAI (mocked SDK)
# ---------------------------------------------------------------------------


def test_openai_provider_summarize_calls_api():
    from src.ai.openai_provider import OpenAIProvider

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Stocks are mixed."))
    ]

    with (
        patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}),
        patch("src.ai.openai_provider.openai.OpenAI", return_value=mock_client),
    ):
        provider = OpenAIProvider()
        result = provider.summarize(SMALL_DATA)

    assert result == "Stocks are mixed."


# ---------------------------------------------------------------------------
# Cloud providers — Perplexity (OpenAI-compatible, mocked)
# ---------------------------------------------------------------------------


def test_perplexity_provider_uses_custom_base_url():
    from src.ai.perplexity import PerplexityProvider

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Regional overview."))
    ]

    with (
        patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"}),
        patch("src.ai.perplexity.openai.OpenAI", return_value=mock_client) as mock_constructor,
    ):
        provider = PerplexityProvider()
        provider.summarize(SMALL_DATA)

    call_kwargs = mock_constructor.call_args[1]
    assert "api.perplexity.ai" in call_kwargs.get("base_url", "")
