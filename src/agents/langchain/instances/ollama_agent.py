"""
Ollama Agent Implementation

基于Ollama本地模型的智能Agent实现
支持完整的工具集成和记忆功能
"""

import logging
from typing import Dict, Any

from src.llm.langchain.instances.ollama_llm import OllamaLLM

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# OKX availability - managed by SDKToolManager
OKX_AVAILABLE = True


class OllamaAgent(BaseAgent):
    """Ollama Agent - Local model based implementation."""

    def __init__(
        self,
        model: str = "gpt-oss:20b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.0,
        verbose: bool = False,
        enable_memory: bool = True,
        global_memory_manager = None,
        disable_thinking_mode: bool = True,
        **kwargs
    ):
        """
        Initialize Ollama Agent.

        Args:
            model: Model name
            base_url: Ollama service URL
            temperature: Temperature parameter (0.0 recommended for agent mode)
            verbose: Enable verbose logging
            enable_memory: Enable memory management
            global_memory_manager: Global memory manager
            disable_thinking_mode: Disable thinking mode for better stability
            **kwargs: Additional parameters
        """
        # Call parent constructor
        super().__init__(
            model=model,
            temperature=temperature,
            verbose=verbose,
            max_iterations=3,  # Lower for local models
            enable_memory=enable_memory,
            global_memory_manager=global_memory_manager,
            **kwargs
        )

        # Ollama-specific configuration
        self.base_url = base_url
        self.disable_thinking_mode = disable_thinking_mode

        logger.info(f"Creating Ollama Agent instance: {model}")

    async def _create_llm_instance(self, llm_params: Dict[str, Any]):
        """使用 LLM Adapter 参数创建 LLM（新接口）"""
        ollama_llm = OllamaLLM(
            model=llm_params.get("model", self.model),
            base_url=self.base_url,
            temperature=llm_params.get("temperature", 0.0),
            **self.kwargs
        )

        # Health check
        health_ok = await ollama_llm.health_check()
        if not health_ok:
            logger.warning("Ollama service health check failed")

        await ollama_llm.initialize()
        self.llm = ollama_llm.create_llm()

        logger.info(f"LLM 创建完成（新方式）: {self.model}")

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