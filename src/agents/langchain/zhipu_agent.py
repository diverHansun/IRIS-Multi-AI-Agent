"""
智谱AI代理模块

智谱AI Agent实现，专注于GLM-4-plus的ReAct功能。
使用外置模板系统和JSON ReAct解析器，支持工具调用和记忆管理。
"""

import logging
from typing import Optional, Dict, Any

from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate

# 导入自定义的 JSON ReAct 输出解析器
from ...components.langchain.parsers.json_react_output_parser import JSONReActSingleInputOutputParser
from ...components.langchain.prompts.registry import PromptRegistry
from ...components.langchain.prompts.tooling import serialize_tools

from ...llm.langchain.zhipu_llm import create_zhipu_llm
from ...llm.langchain.llm_manager import get_llm_info

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ZhipuAgent(BaseAgent):
    """Zhipu AI Agent - Specialized for GLM models with ReAct functionality."""

    def __init__(self,
                 model: str = "glm-4-plus",
                 temperature: float = 0.1,
                 verbose: bool = False,
                 max_iterations: int = 8,
                 enable_memory: bool = True,
                 memory_config: Optional[Dict[str, Any]] = None,
                 global_memory_manager = None,
                 prompt_provider: Optional[str] = None):
        """
        Initialize Zhipu AI Agent.

        Args:
            model: Zhipu AI model name
            temperature: Temperature parameter
            verbose: Enable verbose logging
            max_iterations: Maximum iterations
            enable_memory: Enable memory management
            memory_config: Memory configuration parameters
            global_memory_manager: Global memory manager
            prompt_provider: Prompt template provider
        """
        # Call parent constructor
        super().__init__(
            model=model,
            temperature=temperature,
            verbose=verbose,
            max_iterations=max_iterations,
            enable_memory=enable_memory,
            memory_config=memory_config,
            global_memory_manager=global_memory_manager
        )

        # Zhipu-specific configuration
        self.prompt_provider = prompt_provider or ("glm" if "glm" in model.lower() else None)
    
    async def _create_llm(self):
        """创建LLM实例"""
        # 从配置文件获取模型参数
        model_config = self._get_model_config()
        
        # 优先使用配置文件中的温度设置
        config_temperature = model_config.get("temperature")
        if config_temperature is not None:
            temperature = config_temperature
            logger.info(f"使用配置文件中的温度设置: {temperature}")
        else:
            temperature = self.temperature
            logger.info(f"使用默认温度设置: {temperature}")
        
        llm_config = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": model_config.get("max_tokens", 2048)
        }
        
        self.llm = create_zhipu_llm(**llm_config)
        logger.info(f"LLM创建完成: {self.model}, 温度: {temperature}")
    
    def _get_model_config(self) -> Dict[str, Any]:
        """Get model configuration from config file."""
        try:
            model_info = get_llm_info("zhipu", self.model)

            # Extract temperature from mode_defaults
            mode_defaults = model_info.get("mode_defaults", {})
            llm_defaults = mode_defaults.get("llm", {})
            agent_defaults = mode_defaults.get("agent", {})

            # Priority: llm mode temperature > agent mode temperature
            temperature = llm_defaults.get("temperature") or agent_defaults.get("temperature")

            if temperature is not None:
                model_info["temperature"] = temperature
                logger.info(f"Using temperature from config: {temperature}")

            return model_info
        except Exception as e:
            logger.warning(f"Failed to get model config: {e}, using defaults")
            return {"max_tokens": 2048, "context_window": 128000}
    
    def _build_agent(self):
        """构建Agent - 使用外置模板系统"""
        try:
            # 使用外置模板系统
            template_text = PromptRegistry.get_prompt(
                agent_type="react_json",
                provider=self.prompt_provider,
                locale="zh_CN",
            )
            
            # 准备模板变量
            tools_descriptions = []
            tool_names = []
            for tool in self.tools:
                tools_descriptions.append(f"{tool.name}: {tool.description}")
                tool_names.append(tool.name)
            
            tools_str = "\n".join(tools_descriptions)
            tool_names_str = ", ".join(tool_names)
            
            # 渲染模板
            tools_block = serialize_tools(self.tools)
            rendered = PromptRegistry.render(template_text, tools_block=tools_block)
            
            # 创建PromptTemplate，确保所有变量都能正确替换
            prompt = PromptTemplate.from_template(
                rendered,
                partial_variables={
                    "tools": tools_str,
                    "tool_names": tool_names_str,
                    "agent_scratchpad": ""  # 提供空的agent_scratchpad变量
                }
            )
            
            # 使用JSON ReAct解析器
            output_parser = JSONReActSingleInputOutputParser()
            
            # 创建ReAct Agent
            agent = create_react_agent(self.llm, self.tools, prompt, output_parser=output_parser)
            
            # 配置Agent执行器
            executor_config = {
                "agent": agent,
                "tools": self.tools,
                "verbose": self.verbose,
                "handle_parsing_errors": True,
                "max_iterations": self.max_iterations,
                "early_stopping_method": "force",
                "return_intermediate_steps": True
            }
            
            # GLM-4.5特殊优化
            if self.model == "glm-4.5":
                executor_config.update({
                    "max_iterations": max(self.max_iterations, 15),
                    "max_execution_time": 180,
                })
                logger.info("GLM-4.5优化：增加最大迭代次数和执行时间")
            
            self.agent_executor = AgentExecutor(**executor_config)
            logger.info("Agent执行器创建完成")
            
        except Exception as e:
            logger.error(f"Agent构建失败: {e}")
            raise

    def _get_provider_name(self) -> str:
        """Get provider name for agent info."""
        return "zhipu"


# 兼容性函数，保持向后兼容
async def build_zhipu_agent(
    model: str = "glm-4-plus",
    verbose: bool = False,
    temperature: float = 0.1,
    **kwargs
) -> ZhipuAgent:
    """创建并初始化智谱AI Agent"""
    agent = ZhipuAgent(
        model=model,
        temperature=temperature,
        verbose=verbose,
        **kwargs
    )
    
    await agent.initialize()
    return agent


def build_simple_zhipu_chat(model: str = "glm-4-plus", **kwargs):
    """创建简单的智谱AI聊天模型（不包含工具）"""
    return create_zhipu_llm(model=model, **kwargs)