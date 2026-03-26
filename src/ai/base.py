"""AI provider base contract."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class MarketInsight:
    summary: str
    anomalies: list[dict]
    trends: dict
    provider: str
    generated_at: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())


class AIProvider(ABC):
    @abstractmethod
    def summarize(self, data: list[dict]) -> str: ...

    @abstractmethod
    def detect_anomalies(self, data: list[dict]) -> list[dict]: ...

    @abstractmethod
    def analyze_trends(self, data: list[dict]) -> dict: ...

    def analyze(self, data: list[dict]) -> MarketInsight:
        """Run all three methods and return a structured MarketInsight."""
        return MarketInsight(
            summary=self.summarize(data),
            anomalies=self.detect_anomalies(data),
            trends=self.analyze_trends(data),
            provider=self.__class__.__name__,
        )
