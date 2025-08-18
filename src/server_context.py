from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from box_ai_agents_toolkit import BoxClient, get_ccg_client, get_oauth_client
from mcp.server.fastmcp import FastMCP


@dataclass
class BoxContext:
    client: BoxClient | None = None


@asynccontextmanager
async def box_lifespan_oauth(server: FastMCP) -> AsyncIterator[BoxContext]:
    """Manage Box client lifecycle with OAuth handling"""
    try:
        client = get_oauth_client()
        yield BoxContext(client=client)
    finally:
        # Cleanup (if needed)
        pass


@asynccontextmanager
async def box_lifespan_ccg(server: FastMCP) -> AsyncIterator[BoxContext]:
    """Manage Box client lifecycle with CCG handling"""
    try:
        client = get_ccg_client()
        yield BoxContext(client=client)
    finally:
        # Cleanup (if needed)
        pass
