"""Perplexity AI provider (OpenAI-compatible API)."""

import json
import os

import openai

from src.ai.base import AIProvider


class PerplexityProvider(AIProvider):

    def __init__(self) -> None:
        self._client = openai.OpenAI(
            api_key=os.environ["PERPLEXITY_API_KEY"],
            base_url="https://api.perplexity.ai",
        )
        self._model = os.getenv("PERPLEXITY_MODEL", "llama-3.1-sonar-small-128k-online")

    def _call(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        return response.choices[0].message.content

    def summarize(self, data: list[dict]) -> str:
        return self._call(
            f"Summarize this stock market data in 2-3 sentences:\n{data[:20]}"
        )

    def detect_anomalies(self, data: list[dict]) -> list[dict]:
        raw = self._call(
            "Return a JSON array of anomalies. Each item: symbol, reason, severity.\n"
            f"{data[:20]}"
        )
        try:
            return json.loads(raw)
        except Exception:
            return []

    def analyze_trends(self, data: list[dict]) -> dict:
        raw = self._call(
            "Return a JSON object with keys direction, notable_movers, confidence.\n"
            f"{data[:20]}"
        )
        try:
            return json.loads(raw)
        except Exception:
            return {"direction": "unknown", "notable_movers": [], "confidence": "low"}
