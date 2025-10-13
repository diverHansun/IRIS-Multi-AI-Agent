"""
Ollama Agent Adapter

Ollama的Agent适配器，处理Agent相关参数和特殊逻辑。
"""

import logging
from typing import Dict, Any

from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate

from typing import Optional

from .base import AgentAdapter
from src.core.langchain.providers.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)


class OllamaAgentAdapter(AgentAdapter):
    """Ollama agent adapter."""

    def __init__(
        self,
        model: Optional[str],
        provider_registry: Optional[ProviderRegistry] = None,
    ):
        super().__init__("OLLAMA", model, provider_registry=provider_registry)

    def get_agent_params(self, **user_params) -> Dict[str, Any]:
        """
        获取Ollama Agent参数

        Ollama特殊逻辑:
        - 本地模型，使用较小的max_iterations(3)避免超时
        - max_execution_time较短(30s)

        Args:
            **user_params: 用户传入的参数

        Returns:
            处理后的Agent参数字典
        """
        # 获取基础参数（已包含mode_defaults + mode_overrides）
        params = super().get_agent_params(**user_params)

        # Ollama特殊逻辑: 本地模型使用保守的默认值
        params.setdefault("max_iterations", 3)
        params.setdefault("max_execution_time", 30)

        logger.debug(f"Ollama {self.model} Agent参数: {params}")

        return params

    def create_agent_executor(self, llm, tools, **params) -> AgentExecutor:
        """
        创建Ollama的AgentExecutor

        Ollama使用ReAct Agent

        Args:
            llm: LLM实例
            tools: 工具列表
            **params: 额外参数

        Returns:
            AgentExecutor实例
        """
        # 获取Agent参数
        agent_params = self.get_agent_params(**params)

        logger.info(f"Ollama {self.model} 使用ReAct Agent")

        # 创建ReAct风格的prompt
        template = """Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought: {agent_scratchpad}"""

        prompt = PromptTemplate.from_template(template)

        # 使用ReAct Agent
        agent = create_react_agent(llm, tools, prompt)

        # 创建AgentExecutor
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=agent_params.get("max_iterations", 3),
            max_execution_time=agent_params.get("max_execution_time", 30),
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
        """Ollama部分模型支持Function Calling，这里简化为不支持"""
        return False

    def get_agent_type(self) -> str:
        """Ollama使用react"""
        return "react"
