"""Setup steps for the IRIS setup wizard."""

from src.core.config.setup.steps.base import SetupStep, StepResult, CheckResult, SetupContext
from src.core.config.setup.steps.llm import LLMSetupStep
from src.core.config.setup.steps.agent import AgentSetupStep
from src.core.config.setup.steps.tools import ToolsSetupStep
from src.core.config.setup.steps.dify import DifySetupStep

__all__ = [
    "SetupStep",
    "StepResult",
    "CheckResult",
    "SetupContext",
    "LLMSetupStep",
    "AgentSetupStep",
    "ToolsSetupStep",
    "DifySetupStep",
]
