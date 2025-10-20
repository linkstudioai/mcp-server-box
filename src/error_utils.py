"""Utility functions for enhanced error handling and logging."""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def format_box_error(exception: Exception, context: str = "") -> str:
    """Format a Box API exception with detailed information for user display.
    
    Args:
        exception: The exception from Box SDK
        context: Additional context about where the error occurred
        
    Returns:
        Formatted error message with status code and details
    """
    error_msg = f"Box API error"
    if context:
        error_msg += f" ({context})"
    
    error_msg += f": {str(exception)}"
    
    # Add HTTP status code if available
    status_code = None
    if hasattr(exception, 'status_code'):
        status_code = exception.status_code
    elif hasattr(exception, 'response') and hasattr(exception.response, 'status_code'):
        status_code = exception.response.status_code
    
    if status_code:
        error_msg += f" [HTTP {status_code}]"
    
    # Add error code if available
    if hasattr(exception, 'code'):
        error_msg += f" (Code: {exception.code})"
    
    return error_msg


def log_box_error_details(exception: Exception, context: str = "", request_info: str = ""):
    """Log detailed Box API error information for debugging.
    
    Args:
        exception: The exception from Box SDK
        context: Additional context about where the error occurred
        request_info: Information about the request that failed
    """
    print(f"❌ [BOX API ERROR] {context}")
    if request_info:
        print(f"   Request: {request_info}")
    
    print(f"   Error Type: {type(exception).__name__}")
    print(f"   Error Message: {str(exception)}")
    
    # Log HTTP status code
    status_code = None
    if hasattr(exception, 'status_code'):
        status_code = exception.status_code
    elif hasattr(exception, 'response') and hasattr(exception.response, 'status_code'):
        status_code = exception.response.status_code
    
    if status_code:
        print(f"   HTTP Status Code: {status_code}")
    
    # Log response body if available
    if hasattr(exception, 'response') and hasattr(exception.response, 'text'):
        try:
            response_text = exception.response.text
            if response_text:
                try:
                    response_json = json.loads(response_text)
                    print(f"   Response Body: {json.dumps(response_json, indent=4)}")
                except json.JSONDecodeError:
                    print(f"   Response Text: {response_text}")
        except Exception:
            pass
    
    # Log additional error attributes
    for attr in ['code', 'reason', 'details', 'context']:
        if hasattr(exception, attr):
            try:
                value = getattr(exception, attr)
                print(f"   {attr.title()}: {value}")
            except Exception:
                pass


def handle_box_api_call(func, *args, context: str = "", **kwargs):
    """Wrapper function to handle Box API calls with enhanced error logging.
    
    Args:
        func: The Box API function to call
        *args: Arguments to pass to the function
        context: Context description for error logging
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        The result of the function call
        
    Raises:
        The original exception after logging detailed error information
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        log_box_error_details(e, context=context)
        raise