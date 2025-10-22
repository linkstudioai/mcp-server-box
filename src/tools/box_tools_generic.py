from typing import cast

from box_ai_agents_toolkit import BoxClient, authorize_app
from mcp.server.fastmcp import Context

from error_utils import format_box_error, log_box_error_details
from middleware import box_access_token_var
from server_context import BoxContext, create_box_client_from_token


def get_box_client(ctx: Context) -> BoxClient:
    """Helper function to get Box client from context.
    
    In OAuth/CCG modes, returns the shared client from lifespan context.
    In delegated mode, creates a client per-request using the token from request state.
    
    Args:
        ctx: The MCP request context
        
    Returns:
        BoxClient: Authenticated Box client
        
    Raises:
        RuntimeError: If no client can be obtained
    """
    # First try to get the shared client from lifespan (OAuth/CCG modes)
    lifespan_client = cast(BoxContext, ctx.request_context.lifespan_context).client
    
    if lifespan_client is not None:
        # OAuth or CCG mode - use shared client
        return lifespan_client
    
    # Delegated mode - create client from request token
    # Try to get token from context variable (set by DelegatedAuthMiddleware)
    box_token = box_access_token_var.get()
    if box_token:
        print(f"✅ [GET_BOX_CLIENT] Retrieved token from context variable")
        return create_box_client_from_token(box_token)
    
    # Fallback: try to get from request state (for compatibility)
    if hasattr(ctx.request_context, 'request') and hasattr(ctx.request_context.request.state, 'box_access_token'):
        box_token = ctx.request_context.request.state.box_access_token
        print(f"✅ [GET_BOX_CLIENT] Retrieved token from request state")
        return create_box_client_from_token(box_token)
    
    print("❌ [GET_BOX_CLIENT] No token found in context variable or request state")
    raise RuntimeError(
        "Box client is not initialized. "
        "In delegated mode, ensure the Authorization Bearer token is provided."
    )


async def box_who_am_i(ctx: Context) -> dict:
    """
    Get the current user's information.
    This is also useful to check the connection status.

    return:
        dict: The current user's information.
    """
    try:
        box_client = get_box_client(ctx)
        return box_client.users.get_user_me().to_dict()
    except Exception as e:
        log_box_error_details(e, context="Getting current user information", request_info="GET /users/me")
        # Re-raise for middleware to handle
        raise


async def box_authorize_app_tool() -> str:
    """
    Authorize the Box application.
    Start the Box app authorization process

    return:
        str: Message
    """
    try:
        result = authorize_app()
        if result:
            return "Box application authorized successfully"
        else:
            return "Box application not authorized"
    except Exception as e:
        log_box_error_details(e, context="Authorizing Box application")
        error_msg = format_box_error(e, "authorization")
        return error_msg
