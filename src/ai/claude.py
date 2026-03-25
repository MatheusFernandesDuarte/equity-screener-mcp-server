"""Claude (Anthropic) AI provider."""

import json
import os

import anthropic

from src.ai.base import AIProvider


class ClaudeProvider(AIProvider):

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    def _call(self, prompt: str) -> str:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    def summarize(self, data: list[dict]) -> str:
        return self._call(
            f"Summarize this stock market data in 2-3 sentences:\n{data[:20]}"
        )

    def detect_anomalies(self, data: list[dict]) -> list[dict]:
        raw = self._call(
            "Return a JSON array of anomalies in this stock data. "
            "Each item must have keys: symbol, reason, severity.\n"
            f"{data[:20]}"
        )
        try:
            return json.loads(raw)
        except Exception:
            return []

    def analyze_trends(self, data: list[dict]) -> dict:
        raw = self._call(
            "Return a JSON object with keys direction, notable_movers, confidence "
            f"for this stock data:\n{data[:20]}"
        )
        try:
            return json.loads(raw)
        except Exception:
            return {"direction": "unknown", "notable_movers": [], "confidence": "low"}
