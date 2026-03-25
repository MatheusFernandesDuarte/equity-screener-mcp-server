# Yahoo Finance Regional Crawler

An AI-native, MCP-enabled regional stock data service. Scrapes Yahoo Finance equity data across regions, persists results in DuckDB, and exposes them as MCP tools that any AI agent can call.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Consumers: MCP tools / CLI                         │
│       ↓                                             │
│  MarketService  ──→  DuckDB (read, always fast)     │
│       │                                             │
│       └──→  ScrapeManager.submit()  [non-blocking]  │
└─────────────────────────────────────────────────────┘
         ↓ (background thread)
┌─────────────────────────────────────────────────────┐
│  ScraperEngine  ──→  Yahoo Finance (Selenium+BS4)   │
│       ↓                                             │
│  DuckDB (write, locked)                             │
└─────────────────────────────────────────────────────┘
```

**Key invariants:**
- MCP tools never block on a browser — always served from DuckDB
- Scraping only happens in background workers via `ScrapeManager`
- Stale-while-revalidate: return cached data, trigger refresh in background
- AI layer is optional and fully offline by default

---

## Quick Start

```bash
# Install dependencies
uv sync

# Scrape a region (persists to DuckDB + CSV)
python run.py Argentina
python run.py "United States"
python run.py Belgium
```

Output goes to `data/outputs/` (CSV) and `data/market.duckdb`.

---

## MCP Integration

### Claude Code / Claude Desktop

Add to your MCP config:

```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "/path/to/yahoo-finance-regional-crawler",
      "env": {
        "MCP_TRANSPORT": "stdio",
        "AI_PROVIDER": "local"
      }
    }
  }
}
```

### HTTP server (remote / multi-client)

```bash
MCP_TRANSPORT=http MCP_PORT=8000 python mcp_server.py
```

### Available tools

| Tool | Description |
|------|-------------|
| `get_stocks_by_region(region)` | Latest cached stocks for a region. Triggers background refresh if stale. |
| `get_top_movers(region, n=10)` | Top N stocks by price from latest snapshot. |
| `search_symbol(symbol)` | Case-insensitive partial match across all scraped regions. |
| `get_market_summary(region)` | AI-generated summary, anomaly detection, and trend analysis. |
| `trigger_refresh(region)` | Manually queue a background scrape. |

---

## AI Providers

Set `AI_PROVIDER`. If the API key is missing, the system falls back to the local rule-based provider automatically.

| Provider | Key required |
|----------|-------------|
| `local` (default) | No |
| `claude` → `ANTHROPIC_API_KEY` | Yes |
| `openai` → `OPENAI_API_KEY` | Yes |
| `perplexity` → `PERPLEXITY_API_KEY` | Yes |

```bash
AI_PROVIDER=claude ANTHROPIC_API_KEY=sk-ant-... python mcp_server.py
```

---

## Docker

```bash
docker compose up                                          # Argentina (default)
docker compose run yahoo-crawler python run.py Belgium     # custom region
```

Data persists to `./data/outputs/` on the host.

---

## Development

```bash
uv sync
uv run pytest tests/ -v    # 105 tests, no browser, no network
```

### Project structure

```
src/
  scraper/     ScraperEngine (Selenium+BS4) + ScrapeManager (background workers)
  storage/     DuckDB schema + StockRepository
  services/    MarketService (SWR cache, freshness, dynamic TTL)
  ai/          AIProvider abstraction + LocalProvider + cloud providers
  mcp/         Tool handlers + stdio/HTTP transports
  app/         CLI orchestrator + factories
  config/      Chrome options
tests/         One test file per module, TDD throughout
mcp_server.py  MCP entrypoint
run.py         CLI entrypoint
```

See [docs/extending-providers.md](docs/extending-providers.md) to add a new AI provider or data source.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `local` | `local`, `claude`, `openai`, `perplexity` |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `http` |
| `MCP_PORT` | `8000` | HTTP transport port |
| `ANTHROPIC_API_KEY` | — | Claude provider |
| `OPENAI_API_KEY` | — | OpenAI provider |
| `PERPLEXITY_API_KEY` | — | Perplexity provider |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | Claude model override |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model override |
| `CHROME_BIN` | — | Chromium binary (Docker) |
| `CHROMEDRIVER_BIN` | `/usr/bin/chromedriver` | ChromeDriver path (Docker) |

---

## License

MIT
