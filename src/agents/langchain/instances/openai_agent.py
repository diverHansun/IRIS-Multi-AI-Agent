"""
OpenAI Agent Implementation

基于OpenAI GPT模型的智能Agent实现
支持完整的工具集成和记忆功能
"""

import logging
import warnings
from typing import Dict, Any, Optional, Iterable

from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.llm.langchain.instances.openai_llm import build_openai_chat

from .base_agent import BaseAgent

__all__ = [
    # 数学工具
    "add_numbers", "calculate_math",
    # 搜索工具
    "get_available_search_tools", "get_available_tavily_tools",
    # 时间工具
    "get_available_time_tools",
    # 高德地图工具
    "get_available_amap_tools",
    # Notion工具
    "get_available_notion_tools",
    # OKX工具
    "get_available_okx_tools",
    # 工具管理器
    "SDKToolManager",
    "ConnectorToolManager"
]

# OKX工具可用性 - 通过工具管理器处理
OKX_AVAILABLE = True  # 由SDKToolManager统一管理

logger = logging.getLogger(__name__)


def _format_exception(e: Exception) -> str:
    """Render rich details for ExceptionGroup/TaskGroup to aid debugging."""
    try:
        if hasattr(e, "exceptions") and isinstance(getattr(e, "exceptions"), Iterable):
            parts = [f"{e.__class__.__name__}: {e}"]
            for idx, se in enumerate(getattr(e, "exceptions")):
                parts.append(f"  [{idx}] {se.__class__.__name__}: {se}")
            return "\n".join(parts)
    except Exception:
        pass
    return f"{e.__class__.__name__}: {e}"

class OpenAIAgent(BaseAgent):
    """OpenAI Agent - Function Calling based implementation."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        verbose: bool = False,
        enable_memory: bool = True,
        global_memory_manager = None,
        **kwargs
    ):
        """
        Initialize OpenAI Agent.

        Args:
            api_key: OpenAI API key
            model: Model name
            temperature: Temperature parameter
            verbose: Enable verbose logging
            enable_memory: Enable memory management
            global_memory_manager: Global memory manager
            **kwargs: Additional parameters
        """
        # Call parent constructor
        super().__init__(
            model=model,
            temperature=temperature,
            verbose=verbose,
            enable_memory=enable_memory,
            global_memory_manager=global_memory_manager,
            **kwargs
        )

        # OpenAI-specific configuration
        self.api_key = api_key

        logger.info(f"Creating OpenAI Agent instance: {model}")

    async def _create_llm_instance(self, llm_params: Dict[str, Any]):
        """使用 LLM Adapter 参数创建 LLM（新接口）"""
        from src.config import settings

        base_url = self.kwargs.get('base_url') or settings.openai_base_url

        self.llm = build_openai_chat(
            api_key=self.api_key,
            model=llm_params.get("model", self.model),
            temperature=llm_params.get("temperature", 0.1),
            streaming=llm_params.get("streaming", False),
            max_tokens=llm_params.get("max_tokens"),
            base_url=base_url
        )

        logger.info(f"LLM 创建完成（新方式）: {self.model}")

    async def _create_llm(self):
        """Create OpenAI LLM instance."""
        logger.info("Creating OpenAI LLM...")

        # Check for custom base_url
        from src.config import settings
        base_url = self.kwargs.get('base_url') or settings.openai_base_url

        # Log API endpoint
        if base_url:
            logger.info(f"Using custom OpenAI API endpoint: {base_url}")
        else:
            logger.info("Using default OpenAI API endpoint")

        # Remove base_url from kwargs to avoid duplication
        filtered_kwargs = {k: v for k, v in self.kwargs.items() if k != 'base_url'}

        self.llm = build_openai_chat(
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            base_url=base_url,
            **filtered_kwargs
        )

    def _build_agent(self):
        """Build OpenAI Function Calling agent."""
        # Simple prompt for Function Calling
        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个智能助手，可以使用工具来帮助用户。"),
            MessagesPlaceholder("chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ])

        # Create OpenAI tools agent
        agent = create_openai_tools_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )

        # Create AgentExecutor
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=self.verbose,
            handle_parsing_errors=True,
            max_iterations=10,
            return_intermediate_steps=True
        )

    def _get_provider_name(self) -> str:
        """Get provider name for agent info."""
        return "openai"


# 便捷构建函数
async def build_openai_agent(
    api_key: str,
    model: str = "gpt-4o-mini",
    verbose: bool = False,
    temperature: float = 0.1,
    enable_memory: bool = True,
    **kwargs
) -> OpenAIAgent:
    """
    构建OpenAI Agent

    .. deprecated:: 4.0
        使用 agent_manager.create_agent('openai', model) 替代。
        此函数将在 v5.0 中移除。

    Args:
        api_key: OpenAI API密钥
        model: 模型名称
        verbose: 是否显示详细信息
        temperature: 温度参数
        enable_memory: 是否启用记忆
        **kwargs: 其他参数

    Returns:
        初始化完成的OpenAIAgent实例
        
    推荐方式::
    
        from src.agents.langchain.managers import agent_manager
        agent = await agent_manager.create_agent('openai', model, verbose=verbose)
    """
    # DEPRECATED v4.0 - Will be removed in v5.0
    # Use: agent_manager.create_agent('openai', model)
    agent = OpenAIAgent(
        api_key=api_key,
        model=model,
        temperature=temperature,
        verbose=verbose,
        enable_memory=enable_memory,
        **kwargs
    )
    
    await agent.initialize()
    return agent


