"""
Setup module for IRIS CLI.

Provides interactive setup wizard and configuration health checker.
"""

from src.core.config.setup.wizard import SetupWizard
from src.core.config.setup.validator import ConfigValidator

__all__ = [
    "SetupWizard",
    "ConfigValidator",
]
