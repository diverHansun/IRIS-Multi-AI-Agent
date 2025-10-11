"""
LLM Adapter Base Class

LLM参数适配器基类，用于统一处理不同LLM提供商的LLM相关配置和参数。
从config/llms/providers.json读取配置，应用mode_overrides和特殊逻辑。

注意: 此Adapter只处理LLM参数(temperature, streaming, max_tokens等)，
      不处理Agent参数(max_iterations等)，Agent参数由AgentAdapter处理。
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class LLMAdapter(ABC):
    """
    LLM适配器抽象基类

    职责:
    - 只处理LLM相关参数 (temperature, streaming, max_tokens, thinking_mode等)
    - 从配置文件的mode_defaults.llm和mode_overrides.llm读取参数
    - 不处理Agent参数 (max_iterations等由AgentAdapter处理)
    """

    def __init__(self, provider: str = None, model: str = None, mode: str = "llm"):
        """
        初始化LLM适配器

        Args:
            provider: LLM提供商 (ZHIPU, OPENAI, OLLAMA)，可选
            model: 模型名称
            mode: 使用模式，固定为"llm"
        """
        self.provider = provider.upper() if provider else None
        self.model = model
        self.mode = "llm"  # 固定为llm模式
        self._config = None
        self._provider_config = None
        self._model_config = None

        # 加载配置
        self.load_config()

    def load_config(self) -> None:
        """从providers.json加载配置"""
        try:
            config_path = Path(__file__).parent.parent.parent.parent.parent / "config" / "llms" / "providers.json"
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)

            # 获取提供商配置
            providers = self._config.get("providers", {})
            self._provider_config = providers.get(self.provider, {})

            if not self._provider_config:
                logger.warning(f"未找到提供商 {self.provider} 的配置")
                return

            # 获取模型特定配置
            models = self._provider_config.get("models", {})
            self._model_config = models.get(self.model, {})

            logger.debug(f"成功加载 {self.provider}/{self.model} 配置")

        except FileNotFoundError:
            logger.error(f"配置文件不存在: {config_path}")
            self._config = {}
            self._provider_config = {}
            self._model_config = {}
        except json.JSONDecodeError as e:
            logger.error(f"配置文件JSON解析失败: {e}")
            self._config = {}
            self._provider_config = {}
            self._model_config = {}
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            self._config = {}
            self._provider_config = {}
            self._model_config = {}

    def get_llm_mode_defaults(self) -> Dict[str, Any]:
        """获取llm模式的默认参数"""
        mode_defaults = self._provider_config.get("mode_defaults", {})
        return mode_defaults.get("llm", {})

    def get_llm_mode_overrides(self) -> Dict[str, Any]:
        """获取模型特定的llm mode_overrides"""
        if not self._model_config:
            return {}

        mode_overrides = self._model_config.get("mode_overrides", {})
        return mode_overrides.get("llm", {})

    def get_base_params(self) -> Dict[str, Any]:
        """
        获取基础LLM参数（合并默认值和覆盖值）

        Returns:
            合并后的LLM参数字典
        """
        # 从mode_defaults.llm开始
        params = self.get_llm_mode_defaults().copy()

        # 应用mode_overrides.llm
        overrides = self.get_llm_mode_overrides()
        params.update(overrides)

        return params

    @abstractmethod
    def get_llm_params(self, **kwargs) -> Dict[str, Any]:
        """
        获取LLM参数（包含特殊逻辑处理）

        子类必须实现此方法来处理提供商特定的逻辑。

        处理的参数包括:
        - temperature: 温度参数
        - streaming: 是否流式输出
        - max_tokens: 最大输出token数
        - thinking_mode: 思考模式 (智谱AI特有)
        等

        不处理Agent参数(max_iterations, max_execution_time等)

        Args:
            **kwargs: 用户传入的额外参数

        Returns:
            处理后的LLM参数字典
        """
        pass

    def merge_user_params(self, base_params: Dict[str, Any], user_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并用户参数到基础参数

        Args:
            base_params: 基础参数（从配置读取）
            user_params: 用户传入的参数

        Returns:
            合并后的参数字典
        """
        result = base_params.copy()

        # 用户参数覆盖基础参数
        for key, value in user_params.items():
            if value is not None:  # 只有非None值才覆盖
                result[key] = value

        return result

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型元信息"""
        return {
            "provider": self.provider,
            "model": self.model,
            "mode": self.mode,
            "name": self._model_config.get("name", self.model),
            "description": self._model_config.get("description", ""),
            "supports_tools": self._model_config.get("supports_tools", False),
            "max_tokens": self._model_config.get("max_tokens"),
            "context_window": self._model_config.get("context_window"),
            "model_features": self._model_config.get("model_features", []),
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.provider}, model={self.model}, mode={self.mode})"
