"""
Tavily Search Error Handler Module

Provides enterprise-grade error handling for all Tavily API operations:
- Structured error responses with actionable suggestions
- Automatic retry with exponential backoff
- Detailed error classification and logging
- DRY principle: Unified error handling across all tools

Design Principles:
- KISS: Simple, consistent error handling pattern
- DRY: Single source of truth for error logic
- SOLID: Single responsibility for each error handler
- YAGNI: Only handle errors we've actually encountered
"""

from __future__ import annotations

import time
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Callable, Optional, TypeVar, Tuple
from functools import wraps

# Import all requests exception types
from requests.exceptions import (
    Timeout,
    ConnectionError,
    HTTPError,
    RequestException,
    ConnectTimeout,
    ReadTimeout,
    SSLError,
    ProxyError,
    TooManyRedirects,
)

logger = logging.getLogger(__name__)

# Type variable for retry decorator
T = TypeVar('T')


# ============================================================================
# Error Type Classification
# ============================================================================

class TavilyErrorType(Enum):
    """Comprehensive classification of Tavily API errors"""

    # Configuration errors
    CONFIGURATION_ERROR = "configuration_error"

    # Network and connection errors
    TIMEOUT = "timeout"
    CONNECT_TIMEOUT = "connect_timeout"
    READ_TIMEOUT = "read_timeout"
    NETWORK_ERROR = "network_error"
    SSL_ERROR = "ssl_error"
    PROXY_ERROR = "proxy_error"

    # HTTP errors
    AUTHENTICATION_ERROR = "authentication_error"  # 401
    FORBIDDEN = "forbidden"  # 403
    NOT_FOUND = "not_found"  # 404
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"  # 429
    SERVER_ERROR = "server_error"  # 5xx
    BAD_REQUEST = "bad_request"  # 400

    # Validation errors
    VALIDATION_ERROR = "validation_error"
    INVALID_PARAMETER = "invalid_parameter"

    # Redirect errors
    TOO_MANY_REDIRECTS = "too_many_redirects"

    # Unknown errors
    UNKNOWN_ERROR = "unknown_error"


# ============================================================================
# Error Response Structure
# ============================================================================

@dataclass
class TavilyErrorResponse:
    """Structured error response with actionable information"""

    status: str = "error"
    error_type: str = ""
    message: str = ""
    suggestion: str = ""
    details: Optional[Dict[str, Any]] = None
    retry_after: Optional[int] = None  # Seconds to wait before retry

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            "status": self.status,
            "error_type": self.error_type,
            "message": self.message,
            "suggestion": self.suggestion
        }
        if self.details:
            result["details"] = self.details
        if self.retry_after:
            result["retry_after"] = self.retry_after
        return result


# ============================================================================
# Retry Strategy with Exponential Backoff
# ============================================================================

class RetryStrategy:
    """Implements retry logic with exponential backoff"""

    # Errors that are worth retrying
    RETRIABLE_EXCEPTIONS = (
        Timeout,
        ConnectTimeout,
        ReadTimeout,
        ConnectionError,
        ProxyError,
    )

    @staticmethod
    def should_retry_http_error(status_code: int) -> bool:
        """Determine if an HTTP error is worth retrying"""
        # Retry on server errors (5xx) and rate limit (429)
        return status_code == 429 or status_code >= 500

    @staticmethod
    def calculate_backoff_delay(
        attempt: int,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 60.0
    ) -> float:
        """Calculate exponential backoff delay"""
        delay = initial_delay * (backoff_factor ** attempt)
        return min(delay, max_delay)

    @classmethod
    def execute_with_retry(
        cls,
        func: Callable[[], T],
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        operation_name: str = "operation"
    ) -> T:
        """
        Execute a function with automatic retry on transient errors.

        Args:
            func: Function to execute
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            backoff_factor: Multiplier for each retry
            operation_name: Name of operation for logging

        Returns:
            Result from successful function execution

        Raises:
            Last exception if all retries are exhausted
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                logger.debug(f"Attempt {attempt + 1}/{max_retries} for {operation_name}")
                return func()

            except cls.RETRIABLE_EXCEPTIONS as e:
                last_exception = e
                if attempt == max_retries - 1:
                    # Last attempt failed, raise the exception
                    logger.error(
                        f"{operation_name} failed after {max_retries} attempts: {e}"
                    )
                    raise

                # Calculate delay and retry
                delay = cls.calculate_backoff_delay(attempt, initial_delay, backoff_factor)
                logger.warning(
                    f"{operation_name} attempt {attempt + 1} failed: {e.__class__.__name__}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)

            except HTTPError as e:
                # Check if HTTP error is retriable
                status_code = e.response.status_code if e.response else 0
                if cls.should_retry_http_error(status_code):
                    last_exception = e
                    if attempt == max_retries - 1:
                        raise

                    # For 429, check Retry-After header
                    retry_after = None
                    if status_code == 429 and e.response:
                        retry_after = e.response.headers.get('Retry-After')
                        if retry_after:
                            try:
                                delay = float(retry_after)
                            except ValueError:
                                delay = cls.calculate_backoff_delay(attempt, initial_delay, backoff_factor)
                        else:
                            delay = cls.calculate_backoff_delay(attempt, initial_delay, backoff_factor)
                    else:
                        delay = cls.calculate_backoff_delay(attempt, initial_delay, backoff_factor)

                    logger.warning(
                        f"{operation_name} got HTTP {status_code}. Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    # Non-retriable HTTP error, raise immediately
                    raise

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception


# ============================================================================
# Main Error Handler
# ============================================================================

class TavilyErrorHandler:
    """
    Centralized error handler for all Tavily operations.

    Provides:
    - Detailed error classification
    - User-friendly error messages
    - Actionable suggestions
    - Automatic retry for transient errors
    """

    @staticmethod
    def handle_configuration_error(message: str = None) -> Dict[str, Any]:
        """Handle API key configuration errors"""
        return TavilyErrorResponse(
            error_type=TavilyErrorType.CONFIGURATION_ERROR.value,
            message=message or "Tavily API key not configured",
            suggestion="Set TAVILY_API_KEY environment variable with your API key"
        ).to_dict()

    @staticmethod
    def handle_timeout_error(
        error: Timeout,
        timeout_seconds: int = 30,
        error_type: str = None
    ) -> Dict[str, Any]:
        """Handle timeout errors with specific type"""
        if isinstance(error, ConnectTimeout):
            error_type = TavilyErrorType.CONNECT_TIMEOUT.value
            message = "Connection to Tavily API timed out"
            suggestion = "Check network connection and firewall settings"
        elif isinstance(error, ReadTimeout):
            error_type = TavilyErrorType.READ_TIMEOUT.value
            message = f"Request timed out after {timeout_seconds}s waiting for response"
            suggestion = "Try a simpler query or increase timeout setting"
        else:
            error_type = TavilyErrorType.TIMEOUT.value
            message = f"Request timed out after {timeout_seconds}s"
            suggestion = "Check network speed and try again with a simpler query"

        return TavilyErrorResponse(
            error_type=error_type,
            message=message,
            suggestion=suggestion,
            details={"timeout_seconds": timeout_seconds}
        ).to_dict()

    @staticmethod
    def handle_http_error(error: HTTPError) -> Dict[str, Any]:
        """Handle HTTP errors with detailed status code handling"""
        status_code = error.response.status_code if error.response else 0

        # Map status codes to error types and messages
        error_map = {
            400: (
                TavilyErrorType.BAD_REQUEST,
                "Invalid request parameters",
                "Verify query format and parameters"
            ),
            401: (
                TavilyErrorType.AUTHENTICATION_ERROR,
                "Invalid or missing API key",
                "Verify TAVILY_API_KEY environment variable is correct"
            ),
            403: (
                TavilyErrorType.FORBIDDEN,
                "Access forbidden - insufficient permissions",
                "Check API key permissions or upgrade your plan"
            ),
            404: (
                TavilyErrorType.NOT_FOUND,
                "Resource not found",
                "Verify the request URL and parameters"
            ),
            429: (
                TavilyErrorType.RATE_LIMIT_EXCEEDED,
                "API rate limit exceeded",
                "Wait before retrying, or upgrade your Tavily plan for higher limits"
            ),
        }

        # Check for known status codes
        if status_code in error_map:
            error_type, message, suggestion = error_map[status_code]

            # For rate limit, try to get retry-after header
            retry_after = None
            if status_code == 429 and error.response:
                retry_header = error.response.headers.get('Retry-After')
                if retry_header:
                    try:
                        retry_after = int(retry_header)
                    except ValueError:
                        pass

            return TavilyErrorResponse(
                error_type=error_type.value,
                message=message,
                suggestion=suggestion,
                details={"status_code": status_code},
                retry_after=retry_after
            ).to_dict()

        # Server errors (5xx)
        elif status_code >= 500:
            return TavilyErrorResponse(
                error_type=TavilyErrorType.SERVER_ERROR.value,
                message=f"Tavily service error (HTTP {status_code})",
                suggestion="Service temporarily unavailable, try again in a few moments",
                details={"status_code": status_code}
            ).to_dict()

        # Unknown HTTP error
        else:
            return TavilyErrorResponse(
                error_type=TavilyErrorType.UNKNOWN_ERROR.value,
                message=f"HTTP {status_code}: {str(error)}",
                suggestion="Check Tavily API documentation for this error code",
                details={"status_code": status_code}
            ).to_dict()

    @staticmethod
    def handle_network_error(error: Exception) -> Dict[str, Any]:
        """Handle network-related errors"""
        if isinstance(error, SSLError):
            return TavilyErrorResponse(
                error_type=TavilyErrorType.SSL_ERROR.value,
                message="SSL certificate verification failed",
                suggestion="Check system SSL certificates or network security settings"
            ).to_dict()

        elif isinstance(error, ProxyError):
            return TavilyErrorResponse(
                error_type=TavilyErrorType.PROXY_ERROR.value,
                message="Proxy connection failed",
                suggestion="Check proxy configuration and credentials"
            ).to_dict()

        elif isinstance(error, ConnectionError):
            return TavilyErrorResponse(
                error_type=TavilyErrorType.NETWORK_ERROR.value,
                message="Network connection failed",
                suggestion="Check internet connection, firewall, and DNS settings"
            ).to_dict()

        else:
            return TavilyErrorResponse(
                error_type=TavilyErrorType.NETWORK_ERROR.value,
                message=f"Network error: {str(error)}",
                suggestion="Check network connectivity and try again"
            ).to_dict()

    @staticmethod
    def handle_validation_error(error: ValueError, parameter: str = None) -> Dict[str, Any]:
        """Handle input validation errors"""
        message = str(error)
        details = {}
        if parameter:
            details["parameter"] = parameter

        return TavilyErrorResponse(
            error_type=TavilyErrorType.VALIDATION_ERROR.value,
            message=f"Invalid input: {message}",
            suggestion="Verify query parameters and format",
            details=details if details else None
        ).to_dict()

    @staticmethod
    def handle_redirect_error(error: TooManyRedirects) -> Dict[str, Any]:
        """Handle too many redirects error"""
        return TavilyErrorResponse(
            error_type=TavilyErrorType.TOO_MANY_REDIRECTS.value,
            message="Too many redirects encountered",
            suggestion="Check the URL or contact Tavily support"
        ).to_dict()

    @classmethod
    def handle_error(
        cls,
        error: Exception,
        operation: str = "search",
        timeout_seconds: int = 30
    ) -> Dict[str, Any]:
        """
        Main error handler - routes to specific handlers based on error type.

        Args:
            error: Exception that occurred
            operation: Name of operation that failed (for logging)
            timeout_seconds: Timeout value used (for timeout errors)

        Returns:
            Structured error response dictionary
        """
        # Log the error with full traceback
        logger.error(
            f"Tavily {operation} error: {error.__class__.__name__}: {error}",
            exc_info=True
        )

        # Route to specific handler
        if isinstance(error, (Timeout, ConnectTimeout, ReadTimeout)):
            return cls.handle_timeout_error(error, timeout_seconds)

        elif isinstance(error, HTTPError):
            return cls.handle_http_error(error)

        elif isinstance(error, TooManyRedirects):
            return cls.handle_redirect_error(error)

        elif isinstance(error, (SSLError, ProxyError, ConnectionError)):
            return cls.handle_network_error(error)

        elif isinstance(error, ValueError):
            return cls.handle_validation_error(error)

        else:
            # Unknown error
            logger.error(f"Unexpected Tavily error: {error}", exc_info=True)
            return TavilyErrorResponse(
                error_type=TavilyErrorType.UNKNOWN_ERROR.value,
                message=f"Unexpected error: {str(error)}",
                suggestion="Contact support if this error persists",
                details={
                    "error_class": error.__class__.__name__,
                    "error_module": error.__class__.__module__
                }
            ).to_dict()


# ============================================================================
# Decorator for Tool Functions
# ============================================================================

def with_tavily_error_handling(operation_name: str):
    """
    Decorator to add comprehensive error handling to Tavily tool functions.

    Usage:
        @tool
        @with_tavily_error_handling("search")
        def tavily_search_basic(query: str) -> Dict[str, Any]:
            # Tool implementation
            pass

    Args:
        operation_name: Name of the operation for logging and error messages
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Dict[str, Any]:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                return TavilyErrorHandler.handle_error(
                    e,
                    operation=operation_name,
                    timeout_seconds=kwargs.get('timeout', 30)
                )
        return wrapper
    return decorator


# ============================================================================
# Utility Functions
# ============================================================================

def create_success_response(data: Any, operation: str = "operation") -> Dict[str, Any]:
    """
    Create a standardized success response.

    Args:
        data: The successful result data
        operation: Name of the operation

    Returns:
        Structured success response
    """
    if isinstance(data, dict) and "status" not in data:
        data["status"] = "success"
    return data


def is_error_response(response: Dict[str, Any]) -> bool:
    """
    Check if a response is an error response.

    Args:
        response: Response dictionary to check

    Returns:
        True if response indicates an error
    """
    return response.get("status") == "error" or "error_type" in response
