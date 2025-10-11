"""
OpenAI Agent Adapter

OpenAI的Agent适配器，处理Agent相关参数和特殊逻辑。
"""

import logging
from typing import Dict, Any

from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from .base import AgentAdapter

logger = logging.getLogger(__name__)


class OpenAIAgentAdapter(AgentAdapter):
    """OpenAI Agent适配器"""

    def __init__(self, provider: str, model: str):
        super().__init__(provider="OPENAI", model=model)

    def get_agent_params(self, **user_params) -> Dict[str, Any]:
        """
        获取OpenAI Agent参数

        OpenAI特殊逻辑:
        - 所有OpenAI模型都支持Function Calling
        - 使用配置文件中的agent参数

        Args:
            **user_params: 用户传入的参数

        Returns:
            处理后的Agent参数字典
        """
        # 获取基础参数（已包含mode_defaults + mode_overrides）
        params = super().get_agent_params(**user_params)

        logger.debug(f"OpenAI {self.model} Agent参数: {params}")

        return params

    def create_agent_executor(self, llm, tools, **params) -> AgentExecutor:
        """
        创建OpenAI的AgentExecutor

        OpenAI所有模型都使用Tool Calling Agent

        Args:
            llm: LLM实例
            tools: 工具列表
            **params: 额外参数

        Returns:
            AgentExecutor实例
        """
        # 获取Agent参数
        agent_params = self.get_agent_params(**params)

        logger.info(f"OpenAI {self.model} 使用Tool Calling Agent")

        # 创建OpenAI风格的prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant. Use the provided tools to answer questions."),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # 使用Tool Calling Agent
        agent = create_tool_calling_agent(llm, tools, prompt)

        # 创建AgentExecutor
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=agent_params.get("max_iterations", 10),
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
        """OpenAI所有模型都支持Function Calling"""
        return True

    def get_agent_type(self) -> str:
        """OpenAI使用function_calling"""
        return "function_calling"
