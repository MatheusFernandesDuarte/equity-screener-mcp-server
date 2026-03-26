# Yahoo Finance Regional Crawler

**Ask your AI assistant about stock markets in any country — and get real answers, not hallucinations.**

This project scrapes Yahoo Finance equity data for any region, stores it locally, and exposes it as tools that AI agents (Claude, GPT, or any MCP client) can call. Instead of the AI making up stock prices, it queries your local database.

**Practical example:**
> "What are the top movers in Brazil today?" → Claude calls `get_top_movers("Brazil")` → gets live data from your database → answers accurately.

No more hallucinated tickers. No more stale training-data answers. The AI gets real numbers.

---

## What problem does it solve?

AI assistants don't have access to real-time stock data. When you ask "what's happening in the Argentine market today?", they either refuse or make things up.

This project gives your AI a tool it can actually call. You run the MCP server once, point your AI client at it, and from that moment your assistant can query any scraped region on demand — with fresh data, anomaly detection, and AI-generated summaries.

---

## Quick Start

```bash
# Install dependencies
uv sync

# Scrape a region (stores data locally in DuckDB + CSV)
python run.py Argentina
python run.py "United States"
python run.py Belgium

# Start the MCP server so your AI can query the data
python mcp_server.py
```

Output goes to `data/outputs/` (CSV) and `data/market.duckdb`.

---

## Connect to Claude (or any MCP client)

Add to your MCP config (`~/.claude/claude_desktop_config.json` or Claude Code settings):

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

Now ask Claude:
- *"What are the top 10 stocks in Japan right now?"*
- *"Are there any anomalies in the Brazilian market today?"*
- *"Give me a market summary for Argentina."*
- *"Find any ticker with 'petro' in the name."*

Claude will call the tools, fetch live data from your local database, and answer with real numbers.

---

## What the AI can do

| Tool | What it does |
|------|-------------|
| `get_stocks_by_region(region)` | Returns the latest snapshot for a region. Triggers a background refresh if data is stale. |
| `get_top_movers(region, n=10)` | Top N stocks by price from the latest snapshot. |
| `search_symbol(symbol)` | Find any ticker across all scraped regions. Partial match, case-insensitive. |
| `get_market_summary(region)` | AI-generated summary with anomaly detection and trend analysis. |
| `trigger_refresh(region)` | Queue a fresh scrape in the background without blocking. |

The AI never waits for a browser — responses always come from the local database. Scraping happens in background workers.

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

## HTTP server (remote / multi-client)

```bash
MCP_TRANSPORT=http MCP_PORT=8000 python mcp_server.py
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
