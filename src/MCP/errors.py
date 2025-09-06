class MCPConfigError(Exception):
    """Raised when MCP configuration is invalid or missing required fields."""


class MCPNotAvailableError(Exception):
    """Raised when MCP dependencies are not installed or initialization fails."""


class MCPInitializationError(Exception):
    """Raised for unexpected errors during MCP initialization."""

