"""
Unit tests for Tavily Error Handler Module

Tests all error classification, retry logic, and structured error response functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from requests.exceptions import (
    Timeout,
    ConnectionError,
    HTTPError,
    ConnectTimeout,
    ReadTimeout,
    SSLError,
    ProxyError,
    TooManyRedirects,
)

from src.components.shared.tools.sdk.tavily_search.error_handler import (
    TavilyErrorType,
    TavilyErrorResponse,
    TavilyErrorHandler,
    RetryStrategy,
    create_success_response,
    is_error_response,
)


class TestTavilyErrorResponse:
    """Test TavilyErrorResponse dataclass"""

    def test_to_dict_basic(self):
        """Test basic error response conversion to dict"""
        response = TavilyErrorResponse(
            error_type=TavilyErrorType.TIMEOUT.value,
            message="Request timed out",
            suggestion="Try again"
        )
        result = response.to_dict()

        assert result["status"] == "error"
        assert result["error_type"] == "timeout"
        assert result["message"] == "Request timed out"
        assert result["suggestion"] == "Try again"
        assert "details" not in result
        assert "retry_after" not in result

    def test_to_dict_with_details(self):
        """Test error response with details and retry_after"""
        response = TavilyErrorResponse(
            error_type=TavilyErrorType.RATE_LIMIT_EXCEEDED.value,
            message="Rate limit exceeded",
            suggestion="Wait before retrying",
            details={"status_code": 429},
            retry_after=60
        )
        result = response.to_dict()

        assert result["details"] == {"status_code": 429}
        assert result["retry_after"] == 60


class TestRetryStrategy:
    """Test RetryStrategy logic"""

    def test_calculate_backoff_delay(self):
        """Test exponential backoff calculation"""
        # Default parameters: initial=1.0, factor=2.0, max=60.0
        assert RetryStrategy.calculate_backoff_delay(0) == 1.0
        assert RetryStrategy.calculate_backoff_delay(1) == 2.0
        assert RetryStrategy.calculate_backoff_delay(2) == 4.0
        assert RetryStrategy.calculate_backoff_delay(3) == 8.0

        # Should cap at max_delay
        assert RetryStrategy.calculate_backoff_delay(10, max_delay=60.0) == 60.0

    def test_calculate_backoff_delay_custom(self):
        """Test backoff with custom parameters"""
        delay = RetryStrategy.calculate_backoff_delay(
            attempt=1,
            initial_delay=0.5,
            backoff_factor=3.0,
            max_delay=10.0
        )
        assert delay == 1.5  # 0.5 * 3^1

    def test_should_retry_http_error(self):
        """Test HTTP error retry decision logic"""
        # Should retry
        assert RetryStrategy.should_retry_http_error(429) is True
        assert RetryStrategy.should_retry_http_error(500) is True
        assert RetryStrategy.should_retry_http_error(502) is True
        assert RetryStrategy.should_retry_http_error(503) is True

        # Should not retry
        assert RetryStrategy.should_retry_http_error(400) is False
        assert RetryStrategy.should_retry_http_error(401) is False
        assert RetryStrategy.should_retry_http_error(403) is False
        assert RetryStrategy.should_retry_http_error(404) is False

    def test_execute_with_retry_success_first_try(self):
        """Test successful execution on first attempt"""
        mock_func = Mock(return_value="success")

        result = RetryStrategy.execute_with_retry(
            mock_func,
            max_retries=3,
            operation_name="test_op"
        )

        assert result == "success"
        assert mock_func.call_count == 1

    def test_execute_with_retry_success_after_retries(self):
        """Test successful execution after retries"""
        mock_func = Mock(side_effect=[
            ConnectionError("Network error"),
            Timeout("Timeout"),
            "success"
        ])

        with patch('time.sleep'):  # Mock sleep to speed up test
            result = RetryStrategy.execute_with_retry(
                mock_func,
                max_retries=3,
                initial_delay=0.1,
                operation_name="test_op"
            )

        assert result == "success"
        assert mock_func.call_count == 3

    def test_execute_with_retry_max_retries_exceeded(self):
        """Test failure after max retries"""
        mock_func = Mock(side_effect=ConnectionError("Network error"))

        with patch('time.sleep'):
            with pytest.raises(ConnectionError):
                RetryStrategy.execute_with_retry(
                    mock_func,
                    max_retries=3,
                    operation_name="test_op"
                )

        assert mock_func.call_count == 3

    def test_execute_with_retry_non_retriable_error(self):
        """Test immediate failure on non-retriable error"""
        mock_func = Mock(side_effect=ValueError("Invalid parameter"))

        with pytest.raises(ValueError):
            RetryStrategy.execute_with_retry(
                mock_func,
                max_retries=3,
                operation_name="test_op"
            )

        # Should fail immediately without retries
        assert mock_func.call_count == 1

    def test_execute_with_retry_http_429(self):
        """Test retry logic for HTTP 429 with Retry-After header"""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '5'}

        http_error = HTTPError()
        http_error.response = mock_response

        mock_func = Mock(side_effect=[http_error, "success"])

        with patch('time.sleep') as mock_sleep:
            result = RetryStrategy.execute_with_retry(
                mock_func,
                max_retries=3,
                operation_name="test_op"
            )

        assert result == "success"
        assert mock_func.call_count == 2
        # Should use Retry-After value
        mock_sleep.assert_called_once_with(5.0)

    def test_execute_with_retry_http_500(self):
        """Test retry logic for HTTP 500 errors"""
        mock_response = Mock()
        mock_response.status_code = 500

        http_error = HTTPError()
        http_error.response = mock_response

        mock_func = Mock(side_effect=[http_error, "success"])

        with patch('time.sleep'):
            result = RetryStrategy.execute_with_retry(
                mock_func,
                max_retries=3,
                operation_name="test_op"
            )

        assert result == "success"
        assert mock_func.call_count == 2


class TestTavilyErrorHandler:
    """Test TavilyErrorHandler error classification and handling"""

    def test_handle_configuration_error(self):
        """Test configuration error handling"""
        result = TavilyErrorHandler.handle_configuration_error()

        assert result["status"] == "error"
        assert result["error_type"] == "configuration_error"
        assert "API key not configured" in result["message"]
        assert "TAVILY_API_KEY" in result["suggestion"]

    def test_handle_configuration_error_custom_message(self):
        """Test configuration error with custom message"""
        result = TavilyErrorHandler.handle_configuration_error(
            message="Custom config error"
        )

        assert result["message"] == "Custom config error"

    def test_handle_timeout_error_connect_timeout(self):
        """Test ConnectTimeout error handling"""
        error = ConnectTimeout("Connection timeout")
        result = TavilyErrorHandler.handle_timeout_error(error, timeout_seconds=30)

        assert result["error_type"] == "connect_timeout"
        assert "Connection to Tavily API timed out" in result["message"]
        assert "network connection" in result["suggestion"].lower()

    def test_handle_timeout_error_read_timeout(self):
        """Test ReadTimeout error handling"""
        error = ReadTimeout("Read timeout")
        result = TavilyErrorHandler.handle_timeout_error(error, timeout_seconds=30)

        assert result["error_type"] == "read_timeout"
        assert "30s" in result["message"]
        assert result["details"]["timeout_seconds"] == 30

    def test_handle_timeout_error_generic(self):
        """Test generic Timeout error handling"""
        error = Timeout("Timeout")
        result = TavilyErrorHandler.handle_timeout_error(error, timeout_seconds=45)

        assert result["error_type"] == "timeout"
        assert "45s" in result["message"]

    def test_handle_http_error_400(self):
        """Test HTTP 400 Bad Request"""
        mock_response = Mock()
        mock_response.status_code = 400

        error = HTTPError()
        error.response = mock_response

        result = TavilyErrorHandler.handle_http_error(error)

        assert result["error_type"] == "bad_request"
        assert "Invalid request parameters" in result["message"]
        assert result["details"]["status_code"] == 400

    def test_handle_http_error_401(self):
        """Test HTTP 401 Authentication Error"""
        mock_response = Mock()
        mock_response.status_code = 401

        error = HTTPError()
        error.response = mock_response

        result = TavilyErrorHandler.handle_http_error(error)

        assert result["error_type"] == "authentication_error"
        assert "Invalid or missing API key" in result["message"]
        assert "TAVILY_API_KEY" in result["suggestion"]

    def test_handle_http_error_403(self):
        """Test HTTP 403 Forbidden"""
        mock_response = Mock()
        mock_response.status_code = 403

        error = HTTPError()
        error.response = mock_response

        result = TavilyErrorHandler.handle_http_error(error)

        assert result["error_type"] == "forbidden"
        assert "Access forbidden" in result["message"]

    def test_handle_http_error_404(self):
        """Test HTTP 404 Not Found"""
        mock_response = Mock()
        mock_response.status_code = 404

        error = HTTPError()
        error.response = mock_response

        result = TavilyErrorHandler.handle_http_error(error)

        assert result["error_type"] == "not_found"
        assert "Resource not found" in result["message"]

    def test_handle_http_error_429(self):
        """Test HTTP 429 Rate Limit Exceeded"""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '60'}

        error = HTTPError()
        error.response = mock_response

        result = TavilyErrorHandler.handle_http_error(error)

        assert result["error_type"] == "rate_limit_exceeded"
        assert "rate limit exceeded" in result["message"].lower()
        assert result["retry_after"] == 60

    def test_handle_http_error_500(self):
        """Test HTTP 500 Server Error"""
        mock_response = Mock()
        mock_response.status_code = 500

        error = HTTPError()
        error.response = mock_response

        result = TavilyErrorHandler.handle_http_error(error)

        assert result["error_type"] == "server_error"
        assert "500" in result["message"]
        assert result["details"]["status_code"] == 500

    def test_handle_http_error_503(self):
        """Test HTTP 503 Service Unavailable"""
        mock_response = Mock()
        mock_response.status_code = 503

        error = HTTPError()
        error.response = mock_response

        result = TavilyErrorHandler.handle_http_error(error)

        assert result["error_type"] == "server_error"
        assert "503" in result["message"]

    def test_handle_network_error_ssl(self):
        """Test SSL error handling"""
        error = SSLError("SSL verification failed")
        result = TavilyErrorHandler.handle_network_error(error)

        assert result["error_type"] == "ssl_error"
        assert "SSL certificate verification failed" in result["message"]

    def test_handle_network_error_proxy(self):
        """Test proxy error handling"""
        error = ProxyError("Proxy connection failed")
        result = TavilyErrorHandler.handle_network_error(error)

        assert result["error_type"] == "proxy_error"
        assert "Proxy connection failed" in result["message"]

    def test_handle_network_error_connection(self):
        """Test connection error handling"""
        error = ConnectionError("Network connection failed")
        result = TavilyErrorHandler.handle_network_error(error)

        assert result["error_type"] == "network_error"
        assert "Network connection failed" in result["message"]

    def test_handle_validation_error(self):
        """Test validation error handling"""
        error = ValueError("Invalid parameter value")
        result = TavilyErrorHandler.handle_validation_error(error, parameter="query")

        assert result["error_type"] == "validation_error"
        assert "Invalid input" in result["message"]
        assert result["details"]["parameter"] == "query"

    def test_handle_redirect_error(self):
        """Test too many redirects error"""
        error = TooManyRedirects("Too many redirects")
        result = TavilyErrorHandler.handle_redirect_error(error)

        assert result["error_type"] == "too_many_redirects"
        assert "Too many redirects" in result["message"]

    def test_handle_error_timeout(self):
        """Test main handle_error with timeout"""
        error = ReadTimeout("Read timeout")
        result = TavilyErrorHandler.handle_error(error, operation="search", timeout_seconds=30)

        assert result["error_type"] == "read_timeout"

    def test_handle_error_http(self):
        """Test main handle_error with HTTP error"""
        mock_response = Mock()
        mock_response.status_code = 401

        error = HTTPError()
        error.response = mock_response

        result = TavilyErrorHandler.handle_error(error, operation="search")

        assert result["error_type"] == "authentication_error"

    def test_handle_error_network(self):
        """Test main handle_error with network error"""
        error = ConnectionError("Connection failed")
        result = TavilyErrorHandler.handle_error(error, operation="search")

        assert result["error_type"] == "network_error"

    def test_handle_error_unknown(self):
        """Test main handle_error with unknown error"""
        error = RuntimeError("Unexpected error")
        result = TavilyErrorHandler.handle_error(error, operation="search")

        assert result["error_type"] == "unknown_error"
        assert "Unexpected error" in result["message"]
        assert result["details"]["error_class"] == "RuntimeError"


class TestUtilityFunctions:
    """Test utility functions"""

    def test_create_success_response_dict_without_status(self):
        """Test success response creation for dict without status"""
        data = {"results": ["result1", "result2"]}
        result = create_success_response(data, operation="search")

        assert result["status"] == "success"
        assert result["results"] == ["result1", "result2"]

    def test_create_success_response_dict_with_status(self):
        """Test success response doesn't override existing status"""
        data = {"status": "completed", "results": []}
        result = create_success_response(data, operation="search")

        assert result["status"] == "completed"  # Should not override

    def test_create_success_response_non_dict(self):
        """Test success response with non-dict data"""
        data = "plain string result"
        result = create_success_response(data, operation="search")

        assert result == "plain string result"

    def test_is_error_response_true_status(self):
        """Test error response detection by status"""
        response = {"status": "error", "message": "Failed"}
        assert is_error_response(response) is True

    def test_is_error_response_true_error_type(self):
        """Test error response detection by error_type"""
        response = {"error_type": "timeout", "message": "Timeout"}
        assert is_error_response(response) is True

    def test_is_error_response_false(self):
        """Test non-error response detection"""
        response = {"status": "success", "results": []}
        assert is_error_response(response) is False

    def test_is_error_response_empty(self):
        """Test empty response"""
        response = {}
        assert is_error_response(response) is False


class TestErrorTypeEnum:
    """Test TavilyErrorType enum"""

    def test_all_error_types_exist(self):
        """Verify all expected error types are defined"""
        expected_types = [
            "CONFIGURATION_ERROR",
            "TIMEOUT",
            "CONNECT_TIMEOUT",
            "READ_TIMEOUT",
            "NETWORK_ERROR",
            "SSL_ERROR",
            "PROXY_ERROR",
            "AUTHENTICATION_ERROR",
            "FORBIDDEN",
            "NOT_FOUND",
            "RATE_LIMIT_EXCEEDED",
            "SERVER_ERROR",
            "BAD_REQUEST",
            "VALIDATION_ERROR",
            "INVALID_PARAMETER",
            "TOO_MANY_REDIRECTS",
            "UNKNOWN_ERROR",
        ]

        for error_type in expected_types:
            assert hasattr(TavilyErrorType, error_type)

    def test_error_type_values(self):
        """Test error type enum values"""
        assert TavilyErrorType.TIMEOUT.value == "timeout"
        assert TavilyErrorType.AUTHENTICATION_ERROR.value == "authentication_error"
        assert TavilyErrorType.RATE_LIMIT_EXCEEDED.value == "rate_limit_exceeded"
