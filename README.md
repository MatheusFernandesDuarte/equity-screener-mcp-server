<div align="center">

# 📈 Yahoo Finance Regional Crawler

**Give your AI assistant real stock market data — from any country, in seconds.**

[![CI](https://github.com/MatheusFernandesDuarte/yahoo-finance-regional-crawler/actions/workflows/ci.yml/badge.svg)](https://github.com/MatheusFernandesDuarte/yahoo-finance-regional-crawler/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-enabled-7c3aed?logo=anthropic&logoColor=white)](https://modelcontextprotocol.io)
[![uv](https://img.shields.io/badge/managed%20with-uv-DE5FE9)](https://docs.astral.sh/uv/)

<br/>

*Tired of asking Claude about the stock market and getting hallucinated tickers?*
*This project fixes that.*

[Getting Started](#-getting-started) · [MCP Setup](#-connect-to-your-ai) · [Tools Reference](#-available-tools) · [Architecture](#️-architecture) · [Contributing](#-contributing)

</div>

---

## 🤔 The Problem

When you ask an AI assistant *"Which stocks spiked in Brazil today?"*, it either:

- ❌ Refuses: *"I don't have access to real-time data"*
- ❌ Hallucinates: Makes up tickers with confident-sounding prices

**This project solves that.** It scrapes Yahoo Finance equity data for any region, stores it locally in DuckDB, and exposes it as MCP tools that AI agents can call directly.

```
You:    "Which stock spiked the most in Argentina today?"
Claude: [calls get_top_movers("argentina", sort_by="change_pct")]
        "NVDA.BA surged 8.3% today, followed by AAPL.BA at +5.1%..."
```

Real data. No hallucinations. No browser needed.

---

## ✨ Features

- **🚀 Fast** — HTTP-based scraper (no Selenium, no ChromeDriver). ~10× faster than browser automation.
- **🗄️ Persistent** — DuckDB stores all snapshots locally. Queries are instant.
- **🔄 Stale-while-revalidate** — AI always gets a response immediately; fresh data loads in background.
- **🤖 AI-native** — 5 MCP tools purpose-built for LLM consumption, with freshness-aware descriptions.
- **🌍 Any region** — Argentina, Brazil, Japan, Germany, India, and [60+ more](#supported-regions).
- **📊 Rich data** — Symbol, name, price, and `change_pct` (daily % change) for every stock.
- **🔌 Multi-provider** — Works with Claude, OpenAI, Perplexity, or fully offline with no API key.

---

## 🚀 Getting Started

**Requirements:** Python 3.11+ and [uv](https://docs.astral.sh/uv/getting-started/installation/)

```bash
# 1. Clone the repo
git clone https://github.com/MatheusFernandesDuarte/yahoo-finance-regional-crawler.git
cd yahoo-finance-regional-crawler

# 2. Install dependencies
uv sync

# 3. Scrape your first region
python run.py Argentina

# 4. Start the MCP server
python mcp_server.py
```

Output goes to `data/outputs/` (CSV) and `data/market.duckdb`.

---

## 🔌 Connect to Your AI

### Claude Code (recommended)

```bash
claude mcp add yahoo-finance -- python /path/to/yahoo-finance-regional-crawler/mcp_server.py
```

### Claude Desktop

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "python",
      "args": ["/path/to/yahoo-finance-regional-crawler/mcp_server.py"],
      "env": {
        "AI_PROVIDER": "local"
      }
    }
  }
}
```

### With Claude AI (richer summaries)

```json
{
  "mcpServers": {
    "yahoo-finance": {
      "command": "python",
      "args": ["/path/to/yahoo-finance-regional-crawler/mcp_server.py"],
      "env": {
        "AI_PROVIDER": "claude",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

---

## 💬 Example Conversations

Once connected, just ask naturally:

> **"Which stock spiked the most in Argentina today?"**
> → Claude calls `get_top_movers("argentina", sort_by="change_pct")` and returns ranked results with % change.

> **"Give me a market summary for Brazil."**
> → Claude calls `get_market_summary("brazil")` — returns AI-generated summary, anomaly detection, and trend analysis.

> **"Find any ticker with 'petro' in the name."**
> → Claude calls `search_symbol("petro")` — partial match across all scraped regions.

> **"Are there anomalies in the Japanese market right now?"**
> → Claude scrapes Japan if needed, analyzes Z-scores, flags statistical outliers.

> **"What are the top 5 most expensive stocks in Germany?"**
> → Claude calls `get_top_movers("germany", n=5, sort_by="price")`.

---

## 🛠️ Available Tools

| Tool | Parameters | What it does |
|------|-----------|-------------|
| `get_stocks_by_region` | `region` | Compact snapshot: count + top 10 + freshness status. Auto-triggers refresh if stale. |
| `get_top_movers` | `region`, `n=10`, `sort_by="price"` | Top N stocks sorted by `price` or `change_pct` (daily % change). |
| `search_symbol` | `symbol` | Case-insensitive partial match across all scraped regions. |
| `get_market_summary` | `region` | AI-generated summary with anomaly detection and trend analysis. |
| `trigger_refresh` | `region` | Queue a background scrape without blocking. |

> **Freshness logic:** Claude checks the `freshness` field (`fresh` / `stale` / `expired`) on every response and decides whether to use cached data or trigger a refresh first.

---

## 🤖 AI Providers

| Provider | Env var | Quality |
|----------|---------|---------|
| `local` *(default)* | None required | Rule-based: Z-score anomalies, median trends. Works offline. |
| `claude` | `ANTHROPIC_API_KEY` | Best narrative summaries and market context. |
| `openai` | `OPENAI_API_KEY` | GPT-4o-mini by default, configurable. |
| `perplexity` | `PERPLEXITY_API_KEY` | Good for combining live web context. |

If the API key is missing, the system **automatically falls back** to `local` — no crashes.

```bash
# Run with Claude AI
AI_PROVIDER=claude ANTHROPIC_API_KEY=sk-ant-... python mcp_server.py

# Run fully offline
python mcp_server.py
```

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────┐
│  Claude / GPT / any MCP client                       │
│       ↓  MCP tool calls                              │
│  MarketService  ──→  DuckDB  (reads, always fast)    │
│       │                                              │
│       └──→  ScrapeManager.submit()  [non-blocking]   │
└──────────────────────────────────────────────────────┘
          ↓ background thread
┌──────────────────────────────────────────────────────┐
│  ScraperEngine  ──→  Yahoo Finance API  (HTTP)       │
│     Auth: GET finance.yahoo.com → cookies → crumb    │
│     Data: POST /v1/finance/screener (JSON)           │
│       ↓                                              │
│  DuckDB  (writes, single lock)                       │
└──────────────────────────────────────────────────────┘
```

**Key design invariants:**
- MCP tools **never block** on a network call — always served from DuckDB
- Scraping only happens in background workers (no Selenium, no Chrome)
- **Stale-while-revalidate**: return cached data instantly, refresh in background
- AI layer is **optional** — runs fully offline by default

---

## 🌍 Supported Regions

<details>
<summary>Click to expand — 60+ regions supported</summary>

| Region | Code | Region | Code |
|--------|------|--------|------|
| Argentina | `ar` | Japan | `jp` |
| Australia | `au` | Malaysia | `my` |
| Austria | `at` | Mexico | `mx` |
| Belgium | `be` | Netherlands | `nl` |
| Brazil | `br` | New Zealand | `nz` |
| Canada | `ca` | Nigeria | `ng` |
| Chile | `cl` | Norway | `no` |
| China | `cn` | Pakistan | `pk` |
| Colombia | `co` | Peru | `pe` |
| Czech Republic | `cz` | Philippines | `ph` |
| Denmark | `dk` | Poland | `pl` |
| Egypt | `eg` | Portugal | `pt` |
| Finland | `fi` | Qatar | `qa` |
| France | `fr` | Romania | `ro` |
| Germany | `de` | Saudi Arabia | `sa` |
| Greece | `gr` | Singapore | `sg` |
| Hong Kong | `hk` | South Africa | `za` |
| Hungary | `hu` | South Korea | `kr` |
| India | `in` | Spain | `es` |
| Indonesia | `id` | Sweden | `se` |
| Ireland | `ie` | Switzerland | `ch` |
| Israel | `il` | Taiwan | `tw` |
| Italy | `it` | Thailand | `th` |
| Jordan | `jo` | Turkey | `tr` |
| Kenya | `ke` | United Arab Emirates | `ae` |
| Kuwait | `kw` | United Kingdom | `gb` |
| Latvia | `lv` | United States | `us` |
| Lithuania | `lt` | Venezuela | `ve` |
| Luxembourg | `lu` | Vietnam | `vn` |

</details>

---

## 🐳 Docker

```bash
# Default: scrape Argentina
docker compose up

# Custom region
docker compose run yahoo-crawler python run.py Brazil

# MCP server via HTTP (for remote clients)
MCP_TRANSPORT=http MCP_PORT=8000 docker compose up
```

Data persists to `./data/outputs/` on the host.

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `local` | `local`, `claude`, `openai`, `perplexity` |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `http` |
| `MCP_PORT` | `8000` | HTTP transport port |
| `ANTHROPIC_API_KEY` | — | Required for `claude` provider |
| `OPENAI_API_KEY` | — | Required for `openai` provider |
| `PERPLEXITY_API_KEY` | — | Required for `perplexity` provider |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | Claude model override |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model override |
| `DUCKDB_PATH` | `data/market.duckdb` | Custom database path |

---

## 🧪 Development

```bash
uv sync
python -m pytest tests/ -v      # 109 tests, no browser, no network
uv run ruff check src/ tests/   # lint
```

### Project structure

```
src/
  scraper/    ScraperEngine (HTTP) + ScrapeManager (background workers)
  storage/    DuckDB schema + StockRepository
  services/   MarketService (SWR cache, freshness, dynamic TTL)
  ai/         AIProvider abstraction + LocalProvider + cloud providers
  mcp/        Tool handlers + stdio/HTTP transports
  app/        CLI orchestrator + factories
tests/        One test file per module, TDD throughout
mcp_server.py MCP entrypoint
run.py        CLI entrypoint
```

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, rules, and how to add a new AI provider or data source.

```bash
# Fork, clone, and get started
git checkout -b feat/your-feature
uv sync
python -m pytest tests/   # must be green before opening a PR
```

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

**Built by [Matheus Fernandes](https://github.com/MatheusFernandesDuarte)**

[![GitHub](https://img.shields.io/badge/GitHub-MatheusFernandesDuarte-181717?logo=github)](https://github.com/MatheusFernandesDuarte)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-matheusfernandesduarte-0A66C2?logo=linkedin)](https://www.linkedin.com/in/matheusfernandesduarte/)
[![X](https://img.shields.io/badge/X-matheusfeeer__-000000?logo=x)](https://x.com/matheusfeeer_)

*If this project helped you, consider giving it a ⭐*

</div>
