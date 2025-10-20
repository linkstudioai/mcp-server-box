"""Authentication middleware for MCP server."""

import logging
import os

from fastapi import Request, status
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route

from config import AuthType, TransportType

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to validate Bearer token authentication.
    Expects the token to be set in the BOX_MCP_SERVER_AUTH_TOKEN environment variable.
    This middleware wont even be loaded if the --no-mcp-server-auth flag is set.
    """

    async def dispatch(self, request: Request, call_next):
        """Validate Bearer token before processing request."""
        # logger.info(f"AuthMiddleware triggered for {request.url}")
        # logger.info(f"Headers: {request.headers}")

        # Always allow OAuth discovery endpoint
        if request.url.path == "/.well-known/oauth-protected-resource":
            logger.info("Allowing OAuth discovery endpoint without authentication")
            return await call_next(request)

        expected_token = os.getenv("BOX_MCP_SERVER_AUTH_TOKEN")

        # if no expected token is set, reject all requests
        if not expected_token:
            logger.warning("No token configured, rejecting all requests")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "No authentication token configured"},
            )

        auth_header = request.headers.get("authorization")
        if not auth_header:
            logger.warning("Missing authorization header")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Missing authorization header"},
            )

        if not auth_header.startswith("Bearer "):
            logger.warning("Invalid authorization header format")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Invalid authorization header"},
            )

        token = auth_header.replace("Bearer ", "")
        if token != expected_token:
            logger.warning("Invalid token")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Invalid token"},
            )

        logger.info("Authentication successful")
        return await call_next(request)


class DelegatedAuthMiddleware(BaseHTTPMiddleware):
    """Middleware for delegated authentication mode (e.g., when behind Pomerium).
    
    In this mode, the Bearer token is the Box OAuth access token itself,
    provided by an upstream proxy that has already handled the OAuth flow.
    This middleware extracts the token and makes it available to request handlers.
    """

    async def dispatch(self, request: Request, call_next):
        """Extract Box access token from Authorization header."""
        # Always allow OAuth discovery endpoint
        if request.url.path == "/.well-known/oauth-protected-resource":
            logger.info("Allowing OAuth discovery endpoint without authentication")
            return await call_next(request)

        auth_header = request.headers.get("authorization")
        if not auth_header:
            logger.warning("Missing authorization header in delegated auth mode")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Missing authorization header with Box token"},
            )

        if not auth_header.startswith("Bearer "):
            logger.warning("Invalid authorization header format")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Invalid authorization header format"},
            )

        # Extract the Box access token
        box_access_token = auth_header.replace("Bearer ", "")
        
        # Store it in request state for use by handlers
        request.state.box_access_token = box_access_token
        logger.info("Box access token extracted from Authorization header")
        
        return await call_next(request)


def add_oauth_discovery_endpoint(app, transport: str) -> None:
    """Add OAuth discovery endpoint to the Starlette app."""

    async def oauth_discovery(request):
        """OAuth 2.0 Protected Resource Metadata endpoint."""
        logger.info("OAuth discovery endpoint called")
        return JSONResponse(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            content={
                "error": "OAuth discovery not implemented for transport: {transport}"
            },
        )
        # return JSONResponse(
        #     {
        #         "resource": "box-mcp-server",
        #         "authorization_servers": [],  # Add your OAuth server URLs here if needed
        #         "bearer_methods_supported": ["header"],
        #         "resource_documentation": "https://github.com/box-community/mcp-server-box",
        #     }
        # )

    # Add the route at the beginning
    app.routes.insert(
        0,
        Route(
            "/.well-known/oauth-protected-resource", oauth_discovery, methods=["GET"]
        ),
    )
    logger.info("Added OAuth discovery endpoint")


def add_auth_middleware(mcp: FastMCP, transport: str, box_auth: str) -> None:
    """Add authentication middleware by wrapping the app creation method.
    
    Args:
        mcp: The FastMCP server instance
        transport: The transport type (sse or streamable-http)
        box_auth: The Box authentication mode (oauth, ccg, or delegated)
    """
    logger.info(f"Setting up auth middleware wrapper for transport: {transport}, box_auth: {box_auth}")
    
    # Select the appropriate middleware based on auth mode
    if box_auth == AuthType.DELEGATED.value:
        middleware_class = DelegatedAuthMiddleware
        logger.info("Using DelegatedAuthMiddleware (token from upstream proxy)")
    else:
        middleware_class = AuthMiddleware
        logger.info("Using standard AuthMiddleware (BOX_MCP_SERVER_AUTH_TOKEN)")

    if transport == TransportType.SSE.value:
        # Store the original method
        original_sse_app = mcp.sse_app

        # Create a wrapper that adds middleware
        def wrapped_sse_app(mount_path: str | None = None):
            logger.info(f"wrapped_sse_app called with mount_path={mount_path}")
            app = original_sse_app(mount_path)
            logger.info(f"Adding middleware to app: {id(app)}")

            # Add OAuth discovery endpoint first (before middleware)
            add_oauth_discovery_endpoint(app, transport)
            # Then add auth middleware
            app.add_middleware(middleware_class)
            logger.info(
                f"Middleware added. App middleware count: {len(app.user_middleware)}"
            )
            return app

        # Replace the method with our wrapper
        mcp.sse_app = wrapped_sse_app
        logger.info("Wrapped sse_app method")

    elif transport == TransportType.STREAMABLE_HTTP.value:
        original_streamable_http_app = mcp.streamable_http_app

        def wrapped_streamable_http_app():
            logger.info("wrapped_streamable_http_app called")
            app = original_streamable_http_app()
            logger.info(f"Adding middleware to app: {id(app)}")

            # Add OAuth discovery endpoint first (before middleware)
            add_oauth_discovery_endpoint(app, transport)

            # Then add auth middleware
            app.add_middleware(middleware_class)
            logger.info(
                f"Middleware added. App middleware count: {len(app.user_middleware)}"
            )
            return app

        mcp.streamable_http_app = wrapped_streamable_http_app
        logger.info("Wrapped streamable_http_app method")
