"""
Agent Adapter Base Class

Agent参数适配器抽象基类，用于统一处理Agent相关的配置和参数。
从config/llms/providers.json读取agent模式配置，应用mode_overrides和特殊逻辑。
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class AgentAdapter(ABC):
    """
    Agent适配器抽象基类

    职责:
    - 只处理Agent相关参数 (max_iterations, max_execution_time, memory_enabled, verbose等)
    - 从配置文件的mode_defaults.agent和mode_overrides.agent读取参数
    - 不处理LLM参数 (temperature, streaming等由LLM Adapter处理)
    """

    def __init__(self, provider: str, model: str):
        """
        初始化Agent适配器

        Args:
            provider: LLM提供商 (ZHIPU, OPENAI, OLLAMA)
            model: 模型名称
        """
        self.provider = provider.upper()
        self.model = model
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

            logger.debug(f"成功加载 {self.provider}/{self.model} 的Agent配置")

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

    def get_agent_mode_defaults(self) -> Dict[str, Any]:
        """获取agent模式的默认参数"""
        mode_defaults = self._provider_config.get("mode_defaults", {})
        return mode_defaults.get("agent", {})

    def get_agent_mode_overrides(self) -> Dict[str, Any]:
        """获取模型特定的agent mode_overrides"""
        if not self._model_config:
            return {}

        mode_overrides = self._model_config.get("mode_overrides", {})
        return mode_overrides.get("agent", {})

    def get_agent_params(self, **user_params) -> Dict[str, Any]:
        """
        获取Agent参数（合并默认值、覆盖值和用户参数）

        处理的参数:
        - max_iterations: 最大迭代次数
        - max_execution_time: 最大执行时间（秒）
        - memory_enabled: 是否启用记忆
        - verbose: 是否详细输出
        - temperature: Agent温度参数（与LLM温度可以不同）
        等

        Args:
            **user_params: 用户传入的参数（优先级最高）

        Returns:
            合并后的Agent参数字典
        """
        # 1. 从mode_defaults.agent开始
        params = self.get_agent_mode_defaults().copy()

        # 2. 应用mode_overrides.agent
        overrides = self.get_agent_mode_overrides()
        params.update(overrides)

        # 3. 应用用户参数（优先级最高）
        for key, value in user_params.items():
            if value is not None:  # 只有非None值才覆盖
                params[key] = value

        logger.debug(f"{self.provider}/{self.model} Agent参数: {params}")

        return params

    @abstractmethod
    def create_agent_executor(self, llm, tools, **params):
        """
        创建AgentExecutor（必须由子类实现）

        子类应该:
        1. 调用get_agent_params()获取配置参数
        2. 根据provider/model特性选择合适的Agent类型(ReAct/Function Calling)
        3. 创建并返回AgentExecutor

        Args:
            llm: LLM实例
            tools: 工具列表
            **params: 额外参数

        Returns:
            AgentExecutor实例
        """
        pass

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型元信息"""
        return {
            "provider": self.provider,
            "model": self.model,
            "name": self._model_config.get("name", self.model),
            "description": self._model_config.get("description", ""),
            "supports_tools": self._model_config.get("supports_tools", False),
            "max_tokens": self._model_config.get("max_tokens"),
            "context_window": self._model_config.get("context_window"),
            "model_features": self._model_config.get("model_features", []),
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.provider}, model={self.model})"
