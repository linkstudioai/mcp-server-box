"""Authentication middleware for MCP server."""

import json
import logging
import os
import traceback
from typing import Any, Dict

from fastapi import Request, status
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route

from config import AuthType, TransportType

logger = logging.getLogger(__name__)


def extract_box_error_details(exception: Exception) -> Dict[str, Any]:
    """Extract detailed error information from Box SDK exceptions.
    
    Args:
        exception: The exception caught from Box SDK
        
    Returns:
        Dict containing detailed error information
    """
    error_details = {
        "error_type": type(exception).__name__,
        "error_message": str(exception),
    }
    
    # Try to extract HTTP status code and response details
    if hasattr(exception, 'status_code'):
        error_details["status_code"] = exception.status_code
    
    if hasattr(exception, 'response'):
        try:
            if hasattr(exception.response, 'status_code'):
                error_details["status_code"] = exception.response.status_code
            if hasattr(exception.response, 'text'):
                try:
                    response_text = exception.response.text
                    # Try to parse as JSON for structured error info
                    if response_text:
                        try:
                            response_json = json.loads(response_text)
                            error_details["response_body"] = response_json
                        except json.JSONDecodeError:
                            error_details["response_text"] = response_text
                except Exception:
                    pass
        except Exception:
            pass
    
    # Check for other common error attributes
    for attr in ['code', 'reason', 'details', 'context']:
        if hasattr(exception, attr):
            try:
                error_details[attr] = getattr(exception, attr)
            except Exception:
                pass
    
    return error_details


class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to catch and log detailed error information from downstream handlers."""
    
    async def dispatch(self, request: Request, call_next):
        """Catch and log detailed error information."""
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            # Extract detailed error information
            error_details = extract_box_error_details(e)
            
            # Log the detailed error
            print(f"❌ [ERROR] Box API call failed:")
            print(f"   Request: {request.method} {request.url.path}")
            print(f"   Error Type: {error_details.get('error_type', 'Unknown')}")
            print(f"   Error Message: {error_details.get('error_message', 'No message')}")
            
            if 'status_code' in error_details:
                print(f"   HTTP Status Code: {error_details['status_code']}")
            
            if 'response_body' in error_details:
                print(f"   Response Body: {json.dumps(error_details['response_body'], indent=2)}")
            elif 'response_text' in error_details:
                print(f"   Response Text: {error_details['response_text']}")
            
            if 'code' in error_details:
                print(f"   Error Code: {error_details['code']}")
            
            if 'reason' in error_details:
                print(f"   Reason: {error_details['reason']}")
            
            # Log stack trace for debugging
            logger.error(f"Detailed error traceback:\n{traceback.format_exc()}")
            
            # Re-raise the exception to be handled by the framework
            raise


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
        # Log incoming request details in delegated mode
        print(f"🔄 [DELEGATED MODE] Received request: {request.method} {request.url.path}")
        
        # Always allow OAuth discovery endpoint
        if request.url.path == "/.well-known/oauth-protected-resource":
            logger.info("Allowing OAuth discovery endpoint without authentication")
            return await call_next(request)

        auth_header = request.headers.get("authorization")
        
        # Print authorization header details
        if auth_header:
            print(f"🔑 [DELEGATED MODE] Authorization header: {auth_header}")
        else:
            print("❌ [DELEGATED MODE] No authorization header found")
        
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
        print("✅ [DELEGATED MODE] Successfully extracted Box access token")
        
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
            # Add error logging middleware
            app.add_middleware(ErrorLoggingMiddleware)
            # Then add auth middleware (auth should be outermost)
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
            # Add error logging middleware
            app.add_middleware(ErrorLoggingMiddleware)
            # Then add auth middleware (auth should be outermost)
            app.add_middleware(middleware_class)
            logger.info(
                f"Middleware added. App middleware count: {len(app.user_middleware)}"
            )
            return app

        mcp.streamable_http_app = wrapped_streamable_http_app
        logger.info("Wrapped streamable_http_app method")
