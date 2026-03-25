"""HTTP/SSE MCP transport — for remote and multi-client usage."""

from mcp.server.fastmcp import FastMCP

from src.ai.base import AIProvider
from src.mcp.tools import register_tools
from src.services.market_service import MarketService


def run_http(service: MarketService, ai_provider: AIProvider, port: int = 8000) -> None:
    mcp = FastMCP("yahoo-finance")
    register_tools(mcp, service, ai_provider)
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
