"""
Ollama Agent Implementation

基于Ollama本地模型的智能Agent实现
支持完整的工具集成和记忆功能
"""

import logging

from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate

from ...llm.langchain.ollama_llm import OllamaLLM

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

    async def _create_llm(self):
        """Create Ollama LLM instance."""
        logger.info("Creating Ollama LLM...")

        # Optimize parameters for agent mode
        agent_kwargs = self.kwargs.copy()

        # Disable thinking mode for better stability
        if self.disable_thinking_mode:
            logger.info("Thinking mode disabled for agent stability")

        ollama_llm = OllamaLLM(
            model=self.model,
            base_url=self.base_url,
            temperature=self.temperature,
            **agent_kwargs
        )

        # Health check
        health_ok = await ollama_llm.health_check()
        if not health_ok:
            logger.warning("Ollama service health check failed, continuing initialization")

        # Async initialization
        await ollama_llm.initialize()
        self.llm = ollama_llm.create_llm()
    
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
    
    def _build_agent(self):
        """Build ReAct agent optimized for local models."""
        # Optimized ReAct prompt template for local models
        react_prompt = PromptTemplate.from_template("""
你是一个智能助手，可以回答问题并使用工具完成任务。

你可以使用以下工具：
{tools}

使用以下格式回答：

Question: 用户的问题
Thought: 你应该思考要做什么
Action: 要执行的动作，应该是[{tool_names}]中的一个
Action Input: 动作的输入
Observation: 动作执行的结果
... (这个Thought/Action/Action Input/Observation序列可以重复N次)
Thought: 我现在知道最终答案了
Final Answer: 给用户的最终回复

重要规则：
1. 必须严格按照上面的格式回答
2. Action必须是可用工具列表中的一个
3. 每次只能执行一个Action
4. 如果不需要工具，直接给出Final Answer
5. 用中文回答用户

开始！

Question: {input}
{agent_scratchpad}""")

        # Create ReAct Agent
        agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=react_prompt
        )

        # Create AgentExecutor with optimized config for local models
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=self.verbose,
            handle_parsing_errors=self._custom_error_handler,
            max_iterations=self.max_iterations,
            max_execution_time=30,
            return_intermediate_steps=False
        )

        logger.info("ReAct Agent created")

    def _get_provider_name(self) -> str:
        """Get provider name for agent info."""
        return "ollama"


# 构建函数
async def build_ollama_agent(
    model: str = "gpt-oss:20b",
    base_url: str = "http://localhost:11434",
    verbose: bool = False,
    temperature: float = 0.0,  # Agent模式默认使用0.0温度
    enable_memory: bool = True,
    global_memory_manager = None,
    disable_thinking_mode: bool = True,  # 默认关闭思考模式
    **kwargs
) -> OllamaAgent:
    """
    构建并初始化Ollama Agent
    
    Args:
        model: 模型名称
        base_url: Ollama服务地址
        verbose: 是否显示详细信息
        temperature: 温度参数（Agent模式建议使用0.0）
        enable_memory: 是否启用记忆功能
        global_memory_manager: 全局记忆管理器
        disable_thinking_mode: 是否关闭思考模式（Agent模式建议True）
        **kwargs: 其他参数
        
    Returns:
        初始化完成的Ollama Agent
    """
    agent = OllamaAgent(
        model=model,
        base_url=base_url,
        verbose=verbose,
        temperature=temperature,
        enable_memory=enable_memory,
        global_memory_manager=global_memory_manager,
        disable_thinking_mode=disable_thinking_mode,
        **kwargs
    )
    
    await agent.initialize()
    return agent