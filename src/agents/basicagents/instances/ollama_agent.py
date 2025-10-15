"""
Ollama Agent Implementation

基于Ollama本地模型的智能Agent实现
支持完整的工具集成和记忆功能
"""

import logging
from typing import Dict, Any

from src.llm.managers import llm_manager
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# OKX availability - managed by SDKToolManager
OKX_AVAILABLE = True


class OllamaAgent(BaseAgent):
    """Ollama Agent - Local model based implementation."""

    def __init__(
        self,
        model: str = "gpt-oss:20b",
        provider: str = "ollama",
        llm_adapter = None,
        agent_adapter = None,
        global_memory_manager = None,
        base_url: str = "http://localhost:11434",
        disable_thinking_mode: bool = True,
        **kwargs
    ):
        """
        Initialize Ollama Agent.

        Args:
            model: Model name
            provider: Provider name
            llm_adapter: LLM adapter
            agent_adapter: Agent adapter
            global_memory_manager: Global memory manager
            base_url: Ollama service URL
            disable_thinking_mode: Disable thinking mode for better stability
            **kwargs: Additional parameters
        """
        # Call parent constructor
        super().__init__(
            model=model,
            provider=provider,
            llm_adapter=llm_adapter,
            agent_adapter=agent_adapter,
            global_memory_manager=global_memory_manager,
            **kwargs
        )

        # Ollama-specific configuration
        self.base_url = base_url
        self.disable_thinking_mode = disable_thinking_mode

        logger.info(f"Creating Ollama Agent instance: {model}")

    async def _create_llm_instance(self, llm_params: Dict[str, Any]):
        """Create LLM instance using processed parameters."""
        params = llm_params.copy()
        params.setdefault("base_url", self.base_url)
        params.setdefault("disable_thinking_mode", self.disable_thinking_mode)

        for key, value in self.kwargs.items():
            if value is not None and key not in params:
                params[key] = value

        if "base_url" in params and params["base_url"]:
            self.base_url = params["base_url"]
        if "temperature" in params and params["temperature"] is not None:
            self.temperature = params["temperature"]

        model_name = params.pop("model", self.model)
        self.model = model_name

        llm = llm_manager.create_llm(
            provider="ollama",
            model=model_name,
            mode="agent",
            **params,
        )

        logger.info("LLM created via adapter: %s, params=%s", model_name, llm_params)
        return llm

    def _custom_error_handler(self, error):
        """
        自定义错误处理函数，专门处理Ollama模型的常见问题
        
        Args:
            error: 解析错误信息
            
        Returns:
            str: 错误处理后的提示信息
        """
        error_msg = str(error).lower()
        
        # 502错误和模型不存在错误处理
        if "502" in error_msg or "bad gateway" in error_msg or "not found" in error_msg:
            return "遇到模型连接错误。请确保：1. Ollama服务正在运行 2. 模型已正确安装。如果问题持续，请切换到其他可用模型。"
        
        # JSON解析错误处理
        if "json" in error_msg or "parsing" in error_msg:
            return "输出格式错误，请按照以下格式重新回答：\nThought: 你的思考\nAction: 工具名称\nAction Input: 工具输入\n或者直接给出Final Answer: 最终回答"
        
        # 工具调用错误
        if "tool" in error_msg or "action" in error_msg:
            return "工具调用出错，请检查工具名称和输入格式，然后重新尝试或直接给出答案。"
        
        # 超时错误
        if "timeout" in error_msg:
            return "处理超时，请简化你的回答或直接给出Final Answer。"
        
        # LLM调用错误
        if "llm" in error_msg or "invoke" in error_msg:
            return "模型调用失败，可能是模型不可用或配置问题。请检查模型状态或切换到其他模型。"
        
        # 通用错误处理
        return f"出现错误: {str(error)}。请重新尝试或使用不同的表达方式。如果问题持续，请直接给出Final Answer。"

    def _get_provider_name(self) -> str:
        """Get provider name for agent info."""
        return "ollama"
