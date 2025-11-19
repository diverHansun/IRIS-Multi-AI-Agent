"""
Memory system configuration constants.

Defines storage paths and agent mode routing for the unified memory architecture.
Following KISS and DRY principles by centralizing all memory-related configuration.
"""

# Storage directory paths for different agent modes
BASIC_LLM_STORAGE_DIR = "data/llm_basicagent/sessions"
DEEP_STORAGE_DIR = "data/deepagent/sessions"

# Agent mode mapping to storage directories
AGENT_MODE_STORAGE_MAP = {
    "basic": BASIC_LLM_STORAGE_DIR,
    "llm": BASIC_LLM_STORAGE_DIR,
    "deep": DEEP_STORAGE_DIR,
}

# Valid agent modes
VALID_AGENT_MODES = frozenset(["basic", "llm", "deep"])

# Default configuration
DEFAULT_MAX_MESSAGES = 50
DEFAULT_AGENT_MODE = "basic"


def get_storage_dir(agent_mode: str) -> str:
    """
    Get storage directory for the given agent mode.

    Args:
        agent_mode: Agent mode identifier ("basic", "llm", or "deep")

    Returns:
        Storage directory path

    Raises:
        ValueError: If agent_mode is invalid
    """
    if agent_mode not in VALID_AGENT_MODES:
        raise ValueError(
            f"Invalid agent_mode '{agent_mode}'. "
            f"Must be one of: {', '.join(VALID_AGENT_MODES)}"
        )
    return AGENT_MODE_STORAGE_MAP[agent_mode]
