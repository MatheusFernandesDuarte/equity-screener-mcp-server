"""stdio MCP transport — for local dev with Claude Code / Claude Desktop."""

from mcp.server.fastmcp import FastMCP

from src.ai.base import AIProvider
from src.mcp.tools import register_tools
from src.services.market_service import MarketService


def run_stdio(service: MarketService, ai_provider: AIProvider) -> None:
    mcp = FastMCP("yahoo-finance")
    register_tools(mcp, service, ai_provider)
    mcp.run(transport="stdio")
