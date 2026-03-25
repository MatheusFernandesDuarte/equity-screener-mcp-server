# Yahoo Finance Service — AI-Native MCP Evolution Design

**Date:** 2026-03-25
**Status:** Approved
**Author:** Brainstorming session

---

## 1. Overview

Evolve the existing Yahoo Finance regional crawler into a modern AI-native, MCP-enabled, production-grade data service. The system must behave as a data service — not a synchronous scraper — with strict separation between request handling, data access, and data collection.

---

## 2. Architecture: Layered Monolith

Single Python process. Three fully isolated execution paths sharing only DuckDB.

### 2.1 Directory Structure

```
yahoo_finance_service/
├── run.py                          # CLI entrypoint (unchanged interface)
├── mcp_server.py                   # MCP server entrypoint [NEW]
├── src/
│   ├── app/
│   │   ├── main.py                 # CLI orchestrator [REFACTOR]
│   │   └── factories.py            # Extended factory [REFACTOR]
│   ├── config/
│   │   └── config.py               # Extended config [REFACTOR]
│   ├── scraper/                    # [NEW]
│   │   ├── engine.py               # Selenium + BS4 (extracted from yahoo_finance_service)
│   │   └── manager.py              # ScrapeManager: queue + deduplication + workers
│   ├── storage/                    # [NEW]
│   │   ├── database.py             # DuckDB connection + schema bootstrap
│   │   └── repository.py          # Query methods
│   ├── services/                   # [REFACTOR]
│   │   └── market_service.py       # Cache orchestration + freshness decisions
│   ├── ai/                         # [NEW]
│   │   ├── base.py                 # AIProvider ABC + MarketInsight dataclass
│   │   ├── local.py                # Rule-based fallback (Z-score, median, no API)
│   │   ├── claude.py               # Anthropic implementation
│   │   ├── openai.py               # OpenAI implementation
│   │   ├── perplexity.py           # Perplexity implementation
│   │   └── factory.py              # Env-driven provider selection + fallback chain
│   └── mcp/                        # [NEW]
│       ├── tools.py                # Tool handlers (transport-agnostic)
│       ├── stdio_server.py         # stdio transport entrypoint
│       └── http_server.py          # HTTP/SSE transport entrypoint
└── tests/
    ├── test_engine.py
    ├── test_repository.py
    ├── test_market_service.py
    ├── test_scrape_manager.py
    ├── test_ai_providers.py
    └── test_mcp_tools.py
```

---

## 3. Data Flow

### Request Path (MCP / CLI)
```
MCP Tool Call
    ↓
MarketService.get_stocks_by_region(region)
    ├─ Repository.get_latest(region)  ──→ DuckDB (read)
    ├─ freshness check → ScrapeManager.submit(region) [non-blocking]
    └─ return cached data immediately with freshness state
```

### Background Path (ScrapeManager worker thread)
```
Queue.get(region)
    ↓
Engine.scrape(region)  ← Selenium + BS4 (ONLY here)
    ↓
Repository.insert_batch(region, rows, scraped_at=batch_ts)  ──→ DuckDB (write, locked)
    ↓
in_progress.discard(region)
```

### AI Path (on-demand)
```
MarketService.get_summary(region)
    ↓
Repository.get_aggregated_for_ai(region, limit=50)  ──→ DuckDB (read, last 24h)
    ↓
AIProvider.summarize(pre_aggregated_data)
    ↓
MarketInsight (structured response)
```

---

## 4. ScrapeManager

```python
class ScrapeManager:
    _in_progress: set[str]       # guards BOTH queue and execution
    _lock: threading.Lock        # protects in_progress mutations
    _write_lock: threading.Lock  # one DuckDB writer at a time
    _queue: queue.Queue
    _executor: ThreadPoolExecutor(max_workers=2)

    def submit(self, region: str) -> bool:
        # Mark in_progress BEFORE enqueue — prevents duplicates in queue
        with self._lock:
            if region in self._in_progress:
                return False
            self._in_progress.add(region)
            self._queue.put(region)
        return True

    def _worker(self):
        region = self._queue.get()
        try:
            batch_ts = datetime.utcnow()   # single timestamp = batch ID
            rows = Engine.scrape(region)
            with self._write_lock:         # exclusive DuckDB write
                Repository.insert_batch(region, rows, scraped_at=batch_ts)
        finally:
            self._in_progress.discard(region)
```

**Rules:**
- `submit()` is the only public method and always returns immediately
- `in_progress` is marked before enqueue, cleared only after write completes
- Single `write_lock` ensures DuckDB never receives concurrent writes

---

## 5. Freshness Model

Three states — not a boolean:

```python
class Freshness(Enum):
    FRESH   = "fresh"    # now < last_scraped + TTL         → serve only
    STALE   = "stale"    # TTL < now < 2×TTL               → serve + background refresh
    EXPIRED = "expired"  # now > 2×TTL                     → serve + mark critical
```

**Dynamic TTL (auto-adaptive, driven by access frequency):**

```python
def compute_ttl(access_count: int) -> int:
    if access_count > 50: return 3_600    # popular: 1h
    if access_count > 10: return 7_200    # moderate: 2h
    return 14_400                          # default: 4h
```

TTL is recomputed and upserted to `region_metadata` on every access.

---

## 6. DuckDB Schema

```sql
-- Append-only market data snapshots
CREATE TABLE stocks (
    region      VARCHAR       NOT NULL,
    symbol      VARCHAR       NOT NULL,
    name        VARCHAR,
    price       DECIMAL(18,4),
    scraped_at  TIMESTAMPTZ   NOT NULL   -- same value per batch = batch ID
);

CREATE INDEX idx_stocks_region_time ON stocks (region, scraped_at DESC);

-- One row per region, upserted on every scrape
CREATE TABLE region_metadata (
    region          VARCHAR     PRIMARY KEY,
    last_scraped_at TIMESTAMPTZ,
    access_count    BIGINT      DEFAULT 0,
    ttl_seconds     INTEGER     DEFAULT 14400
);
```

---

## 7. AI Provider Abstraction

### Interface

```python
@dataclass
class MarketInsight:
    summary: str
    anomalies: list[dict]   # [{symbol, reason, severity}]
    trends: dict            # {direction, notable_movers, confidence}
    provider: str
    generated_at: str

class AIProvider(ABC):
    def summarize(self, data: list[dict]) -> str: ...
    def detect_anomalies(self, data: list[dict]) -> list[dict]: ...
    def analyze_trends(self, data: list[dict]) -> dict: ...
```

### Provider Resolution (fail-safe chain)

```
AI_PROVIDER env var
    ↓
Validate API key present
    ├─ Missing key → warn + fallback to LocalProvider
    └─ Init failure → warn + fallback to LocalProvider

Providers: claude | openai | perplexity | local (default)
```

### LocalProvider (fully offline)
- `summarize`: count, avg price, above/below average count
- `detect_anomalies`: Z-score > 2.0 on price column
- `analyze_trends`: top 5 / bottom 5 by price, median, direction heuristic

### AI Payload Contract
- Max 50 rows per call
- Latest snapshot only (last 24h window)
- Pre-ranked by price (DuckDB does the work, not the LLM)

---

## 8. MCP Tools

All tools are transport-agnostic. All return typed dicts with consistent keys.

| Tool | Input | Output |
|------|-------|--------|
| `get_stocks_by_region` | `region: str` | `{region, stocks, freshness, last_scraped_at}` |
| `get_top_movers` | `region: str, n: int = 10` | `{region, movers: [{symbol, name, price}]}` |
| `search_symbol` | `symbol: str` | `[{region, symbol, name, price, scraped_at}]` |
| `get_market_summary` | `region: str` | `MarketInsight as dict` |
| `trigger_refresh` | `region: str` | `{queued: bool, region: str, message: str}` |

**Hard rule:** No tool ever calls `Engine.scrape()` directly or blocks on I/O.

---

## 9. Transport Layer

```python
# mcp_server.py (root)
transport = os.getenv("MCP_TRANSPORT", "stdio")  # stdio | http
port = int(os.getenv("MCP_PORT", 8000))
```

- `stdio_server.py`: FastMCP with stdio transport (local dev, Claude Code/Desktop)
- `http_server.py`: FastMCP with SSE transport (remote, multi-client)
- Tool registration is identical in both — no logic duplication

**Environment variables:**
```
MCP_TRANSPORT=stdio|http     (default: stdio)
MCP_PORT=8000
AI_PROVIDER=claude|openai|perplexity|local   (default: local)
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
PERPLEXITY_API_KEY=...
CHROME_BIN=...               (Docker only)
CHROMEDRIVER_BIN=...         (Docker only)
```

---

## 10. Testing Strategy

- TDD enforced: tests written before implementation
- All Selenium calls mocked — no live browser in tests
- All DuckDB operations use in-memory DB (`duckdb.connect(':memory:')`)
- All AI provider calls mocked — LocalProvider used as test default
- Tests must be fast (<5s total), deterministic, and isolated

---

## 11. Open Source Readiness

- `CONTRIBUTING.md`: setup, conventions, PR process
- `README.md`: updated with MCP usage, AI configuration, architecture diagram
- `docs/extending-providers.md`: how to add a new scraper or AI provider
- `examples/`: CLI usage, MCP config for Claude Desktop/Code
- Clean git history with conventional commits
