#!/usr/bin/env bash
# CLI usage examples

# Scrape a single region
python run.py Argentina

# Multi-word regions (quotes optional — all args are joined)
python run.py "United States"
python run.py United Kingdom

# Run via Docker
docker compose up
docker compose run yahoo-crawler python run.py Belgium

# Start MCP server (stdio, local AI)
python mcp_server.py

# Start MCP server (HTTP, port 8000, Claude AI)
MCP_TRANSPORT=http \
MCP_PORT=8000 \
AI_PROVIDER=claude \
ANTHROPIC_API_KEY=sk-ant-... \
python mcp_server.py
