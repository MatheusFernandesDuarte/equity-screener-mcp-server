"""MCP server entrypoint.

Usage:
    MCP_TRANSPORT=stdio python mcp_server.py   (default)
    MCP_TRANSPORT=http  MCP_PORT=8000 python mcp_server.py

Claude Desktop / Claude Code config example:
    {
      "mcpServers": {
        "yahoo-finance": {
          "command": "python",
          "args": ["mcp_server.py"],
          "env": {
            "MCP_TRANSPORT": "stdio",
            "AI_PROVIDER": "local"
          }
        }
      }
    }
"""

import os

from src.ai.factory import get_provider
from src.app.factories import create_engine_factory
from src.scraper.manager import ScrapeManager
from src.services.market_service import MarketService
from src.storage.database import get_connection
from src.storage.repository import StockRepository


def main() -> None:
    conn = get_connection()
    repo = StockRepository(conn)
    engine_factory = create_engine_factory()
    manager = ScrapeManager(engine_factory=engine_factory, repository=repo)
    service = MarketService(repository=repo, scrape_manager=manager)
    ai_provider = get_provider()

    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()

    if transport == "http":
        from src.mcp.http_server import run_http
        run_http(service, ai_provider, port=int(os.getenv("MCP_PORT", 8000)))
    else:
        from src.mcp.stdio_server import run_stdio
        run_stdio(service, ai_provider)


if __name__ == "__main__":
    main()
