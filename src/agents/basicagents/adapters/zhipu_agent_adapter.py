"""
Zhipu AI Agent Adapter

智谱AI的Agent适配器，处理Agent相关参数和特殊逻辑。
"""

import logging
from typing import Dict, Any

from langchain.agents import create_react_agent, create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate

from typing import Optional

from .base import AgentAdapter
from src.core.providers.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)


class ZhipuAgentAdapter(AgentAdapter):
    """Zhipu AI agent adapter."""

    def __init__(
        self,
        model: Optional[str],
        provider_registry: Optional[ProviderRegistry] = None,
    ):
        super().__init__("ZHIPU", model, provider_registry=provider_registry)

    def get_agent_params(self, **user_params) -> Dict[str, Any]:
        """
        获取智谱AI Agent参数

        特殊逻辑:
        - glm-4.5/glm-4.5-flash: 使用更高的max_iterations(15)
        - 其他模型: 使用标准配置(8)

        Args:
            **user_params: 用户传入的参数

        Returns:
            处理后的Agent参数字典
        """
        # 获取基础参数（已包含mode_defaults + mode_overrides）
        params = super().get_agent_params(**user_params)

        # 智谱特殊逻辑: glm-4.5系列如果配置中有覆盖，优先使用配置
        if self.model in ["glm-4.5", "glm-4.5-flash"]:
            # mode_overrides中已经定义了max_iterations=15
            # 这里只需确保正确读取即可
            logger.debug(f"{self.model} 使用配置的max_iterations: {params.get('max_iterations')}")

        return params

    def create_agent_executor(self, llm, tools, **params) -> AgentExecutor:
        """
        创建智谱AI的AgentExecutor

        根据模型类型选择:
        - glm-4.5/glm-4.5-flash: Tool Calling Agent (原生Function Calling)
        - 其他模型: ReAct Agent

        Args:
            llm: LLM实例
            tools: 工具列表
            **params: 额外参数

        Returns:
            AgentExecutor实例
        """
        # 获取Agent参数
        agent_params = self.get_agent_params(**params)

        # 根据模型类型选择Agent
        if self.model in ["glm-4.5", "glm-4.5-flash"]:
            # 使用Tool Calling Agent
            logger.info(f"{self.model} 使用Tool Calling Agent")

            # 获取prompt
            from src.components.basicagents.prompts.registry import PromptRegistry
            template_text = PromptRegistry.get_prompt(
                agent_type="tool_calling",
                provider="glm",
                locale="zh_CN",
            )
            prompt = PromptTemplate.from_template(template_text)

            agent = create_tool_calling_agent(llm, tools, prompt)

        else:
            # 使用ReAct Agent
            logger.info(f"{self.model} 使用ReAct Agent")

            # 获取prompt
            from src.components.basicagents.prompts.registry import PromptRegistry
            template_text = PromptRegistry.get_prompt(
                agent_type="react_json",
                provider="glm",
                locale="zh_CN",
            )
            prompt = PromptTemplate.from_template(template_text)

            agent = create_react_agent(llm, tools, prompt)

        # 创建AgentExecutor，使用配置的参数
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=agent_params.get("max_iterations", 8),
            max_execution_time=agent_params.get("max_execution_time"),
            verbose=agent_params.get("verbose", False),
            handle_parsing_errors=True,
            return_intermediate_steps=True,
        )

        logger.info(
            f"AgentExecutor created: max_iterations={agent_params.get('max_iterations')}, "
            f"max_execution_time={agent_params.get('max_execution_time')}"
        )

        return executor

    def supports_function_calling(self) -> bool:
        """判断模型是否支持Function Calling"""
        return self.model in ["glm-4.5", "glm-4.5-flash"]

    def get_agent_type(self) -> str:
        """
        获取推荐的Agent类型

        Returns:
            "function_calling" 或 "react"
        """
        if self.supports_function_calling():
            return "function_calling"
        return "react"
