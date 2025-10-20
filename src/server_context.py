from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from box_ai_agents_toolkit import BoxClient, get_ccg_client, get_oauth_client
from box_sdk_gen import BoxClient as BoxSDKClient, BoxDeveloperTokenAuth
from mcp.server.fastmcp import FastMCP


@dataclass
class BoxContext:
    client: BoxClient | None = None


def create_box_client_from_token(access_token: str) -> BoxClient:
    """Create a Box client using an access token from an upstream proxy.
    
    Args:
        access_token: The Box OAuth access token provided by upstream proxy (e.g., Pomerium)
    
    Returns:
        BoxClient: A Box client authenticated with the provided token
    """
    auth = BoxDeveloperTokenAuth(token=access_token)
    box_client = BoxSDKClient(auth=auth)
    # Add extra header for tracking
    return box_client.with_extra_headers(extra_headers={"x-box-ai-library": "mcp-server-box"})


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


@asynccontextmanager
async def box_lifespan_delegated(server: FastMCP) -> AsyncIterator[BoxContext]:
    """Manage Box client lifecycle with delegated auth (token from upstream proxy).
    
    In this mode, no Box client is created at startup. Instead, clients are created
    per-request using the access token provided by an upstream proxy like Pomerium.
    """
    try:
        # No client created - will be created per-request from token
        yield BoxContext(client=None)
    finally:
        # Cleanup (if needed)
        pass
