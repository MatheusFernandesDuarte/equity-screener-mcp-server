"""LocalProvider — fully offline, rule-based AI fallback."""

import statistics

from src.ai.base import AIProvider


class LocalProvider(AIProvider):

    def summarize(self, data: list[dict]) -> str:
        prices = [r["price"] for r in data if isinstance(r.get("price"), (int, float))]
        if not prices:
            return "No data available."
        avg = statistics.mean(prices)
        above = sum(1 for p in prices if p > avg)
        return (
            f"{len(data)} stocks · avg price {avg:.2f} · "
            f"{above} above average · {len(prices) - above} below average"
        )

    def detect_anomalies(self, data: list[dict]) -> list[dict]:
        prices = [r["price"] for r in data if isinstance(r.get("price"), (int, float))]
        if len(prices) < 3:
            return []
        mean = statistics.mean(prices)
        stdev = statistics.stdev(prices)
        if stdev == 0:
            return []
        result = []
        for row in data:
            price = row.get("price")
            if not isinstance(price, (int, float)):
                continue
            z = abs(price - mean) / stdev
            if z > 2.0:
                result.append({
                    "symbol": row.get("symbol", ""),
                    "price": price,
                    "z_score": round(z, 2),
                    "reason": "price outlier",
                    "severity": "high" if z > 3.0 else "medium",
                })
        return result

    def analyze_trends(self, data: list[dict]) -> dict:
        rows = [r for r in data if isinstance(r.get("price"), (int, float))]
        if not rows:
            return {"direction": "unknown", "notable_movers": [], "confidence": "low"}
        sorted_rows = sorted(rows, key=lambda r: r["price"], reverse=True)
        prices = [r["price"] for r in sorted_rows]
        median = statistics.median(prices)
        direction = "bullish" if sorted_rows[0]["price"] > median * 1.5 else "neutral"
        return {
            "direction": direction,
            "notable_movers": [
                {"symbol": r["symbol"], "price": r["price"]} for r in sorted_rows[:5]
            ],
            "median_price": round(median, 2),
            "confidence": "medium",
        }
