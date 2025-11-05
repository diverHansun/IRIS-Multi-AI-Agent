"""
Unified exception classes for BasicAgents module.

Provides consistent error handling across all layers (Manager, Adapter, Agent).
"""

from typing import List, Optional


class BasicAgentError(Exception):
    """Base exception for all BasicAgent errors."""
    pass


class ConfigurationError(BasicAgentError):
    """
    Configuration validation error.

    Raised when configuration parameters are invalid or missing.
    """

    def __init__(self, message: str, config_key: Optional[str] = None):
        """
        Initialize configuration error.

        Args:
            message: Error description
            config_key: The configuration key that caused the error
        """
        self.config_key = config_key
        super().__init__(message)


class AuthenticationError(BasicAgentError):
    """
    Authentication error for API credentials.

    Raised when API key or authentication credentials are missing or invalid.
    """

    def __init__(self, provider: str, env_var: str):
        """
        Initialize authentication error.

        Args:
            provider: Provider name (e.g., 'zhipu', 'openai')
            env_var: Environment variable name that should contain the API key
        """
        self.provider = provider
        self.env_var = env_var
        message = (
            f"Authentication failed for provider '{provider}'. "
            f"Please set environment variable: {env_var}"
        )
        super().__init__(message)


class ProviderNotFoundError(BasicAgentError):
    """
    Provider not found error.

    Raised when specified provider is not registered.
    """

    def __init__(self, provider: str, available_providers: List[str]):
        """
        Initialize provider not found error.

        Args:
            provider: The provider that was not found
            available_providers: List of available provider names
        """
        self.provider = provider
        self.available_providers = available_providers
        message = (
            f"Provider '{provider}' not found. "
            f"Available providers: {', '.join(available_providers)}"
        )
        super().__init__(message)


class ModelNotFoundError(BasicAgentError):
    """
    Model not found error.

    Raised when specified model is not available for the provider.
    """

    def __init__(self, provider: str, model: str, available_models: List[str]):
        """
        Initialize model not found error.

        Args:
            provider: Provider name
            model: The model that was not found
            available_models: List of available model names for this provider
        """
        self.provider = provider
        self.model = model
        self.available_models = available_models
        message = (
            f"Model '{model}' not found for provider '{provider}'. "
            f"Available models: {', '.join(available_models)}"
        )
        super().__init__(message)


class LLMCreationError(BasicAgentError):
    """
    LLM instance creation error.

    Raised when LLM initialization fails.
    """

    def __init__(self, provider: str, model: str, reason: str):
        """
        Initialize LLM creation error.

        Args:
            provider: Provider name
            model: Model name
            reason: Detailed error reason
        """
        self.provider = provider
        self.model = model
        self.reason = reason
        message = f"Failed to create LLM for {provider}/{model}: {reason}"
        super().__init__(message)


class ToolLoadingError(BasicAgentError):
    """
    Tool loading error.

    Raised when tool initialization fails.
    """
    pass


class GraphCreationError(BasicAgentError):
    """
    Agent graph creation error.

    Raised when LangGraph CompiledStateGraph creation fails.
    """

    def __init__(self, provider: str, model: str, reason: str):
        """
        Initialize graph creation error.

        Args:
            provider: Provider name
            model: Model name
            reason: Detailed error reason
        """
        self.provider = provider
        self.model = model
        self.reason = reason
        message = f"Failed to create agent graph for {provider}/{model}: {reason}"
        super().__init__(message)


class AgentCreationError(BasicAgentError):
    """
    Agent instance creation error.

    Raised when agent instantiation fails.
    """
    pass


class AgentExecutionError(BasicAgentError):
    """
    Agent execution error.

    Raised when agent query execution fails.
    """
    pass


class ExecutionTimeoutError(AgentExecutionError):
    """
    Agent execution timeout error.

    Raised when agent execution exceeds max_execution_time.
    """

    def __init__(self, timeout: int):
        """
        Initialize execution timeout error.

        Args:
            timeout: Maximum execution time in seconds
        """
        self.timeout = timeout
        message = f"Agent execution exceeded maximum time limit: {timeout}s"
        super().__init__(message)
