"""
Ollama Provider Implementation

Ollama Provider实现，负责创建和管理Ollama本地LLM实例。
"""

import logging
from typing import Dict, Any

from src.llm.langchain.providers.base import BaseProvider
from src.llm.langchain.instances.ollama_llm import OllamaLLM

logger = logging.getLogger(__name__)


class OllamaProvider(BaseProvider):
    """
    Ollama Provider实现

    职责:
    - 创建Ollama本地LLM实例
    - 动态检测本地已安装的模型
    - 管理Ollama特定配置
    """

    def create_llm(self, model: str, api_key: str = None, **kwargs):
        """
        创建Ollama LLM实例

        注意: Ollama是本地模型，不需要API密钥

        Args:
            model: 模型名称 (qwen2.5, llama3.1等)
            api_key: 无需API密钥 (忽略)
            **kwargs: 其他参数
                - base_url: Ollama服务地址
                - temperature: 温度参数
                - num_ctx: 上下文窗口大小
                - top_p, top_k: 采样参数

        Returns:
            LangChain兼容的LLM实例

        Raises:
            ValueError: 模型不支持或Ollama服务不可用
        """
        logger.info(f"创建Ollama LLM: {model}")

        # 使用 OllamaLLM 包装器创建实例
        llm_wrapper = OllamaLLM(
            model=model,
            **kwargs
        )

        return llm_wrapper.create_llm()

    def validate_api_key(self, api_key: str) -> bool:
        """
        验证API密钥

        Ollama是本地模型，不需要API密钥，始终返回True

        Args:
            api_key: API密钥 (忽略)

        Returns:
            始终为True
        """
        return True

    def get_supported_models(self) -> Dict[str, Any]:
        """
        获取支持的Ollama模型列表

        优先使用动态检测的本地已安装模型，失败时回退到配置文件

        Returns:
            模型配置字典
        """
        try:
            # 尝试动态检测本地已安装的模型
            dynamic_models = OllamaLLM.get_supported_models()
            if dynamic_models:
                logger.debug(f"动态检测到 {len(dynamic_models)} 个Ollama模型")
                # 合并静态配置和动态检测的模型
                all_models = self.models.copy()
                all_models.update(dynamic_models)
                return all_models
        except Exception as e:
            logger.warning(f"动态检测Ollama模型失败: {e}")

        # 回退到配置文件的静态模型列表
        return self.models

    def validate_model(self, model: str) -> bool:
        """
        验证模型是否支持

        对于Ollama，如果无法动态检测，默认接受任何模型名称

        Args:
            model: 模型名称

        Returns:
            是否支持
        """
        try:
            supported_models = self.get_supported_models()
            return model in supported_models
        except:
            # 如果无法检测，假设用户知道自己在做什么
            logger.warning(f"无法验证Ollama模型 {model}，假设有效")
            return True

    def __repr__(self) -> str:
        try:
            models = list(self.get_supported_models().keys())
            return f"OllamaProvider(name={self.name}, models={models[:5]}...)"
        except:
            return f"OllamaProvider(name={self.name})"
