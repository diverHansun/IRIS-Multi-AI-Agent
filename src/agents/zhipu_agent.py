"""
智谱AI代理模块

智谱AI Agent实现，专注于GLM-4-plus的ReAct功能。
使用外置模板系统和JSON ReAct解析器，支持工具调用和记忆管理。
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any, Union

from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate

# 导入自定义的 JSON ReAct 输出解析器
from ..parsers.json_react_output_parser import JSONReActSingleInputOutputParser
from ..prompts.registry import PromptRegistry
from ..prompts.tooling import serialize_tools

from ..llm.zhipu_llm import create_zhipu_llm
from ..llm.llm_manager import get_llm_info
from ..tools.calculate.math_tools import add_numbers, calculate_math
from ..tools.search.tavily_search_tool import get_available_tavily_tools
from ..tools.amap import get_available_amap_tools
from ..tools.time import get_available_time_tools
from ..memory.global_memory import GlobalMemoryManager

logger = logging.getLogger(__name__)


class ZhipuAgent:
    """简化的智谱AI Agent - 专注于GLM-4-plus的ReAct功能"""
    
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
        初始化智谱AI Agent
        
        Args:
            model: 智谱AI模型名称
            temperature: 温度参数
            verbose: 是否显示详细日志
            max_iterations: 最大迭代次数
            enable_memory: 是否启用记忆功能
            memory_config: 记忆配置参数
            global_memory_manager: 全局记忆管理器
            prompt_provider: 提示模板提供商
        """
        self.model = model
        self.temperature = temperature
        self.verbose = verbose
        self.max_iterations = max_iterations
        self.enable_memory = enable_memory
        self.global_memory_manager = global_memory_manager
        self.prompt_provider = prompt_provider or ("glm" if "glm" in model.lower() else None)
        
        # 核心组件
        self.llm = None
        self.tools = []
        self.agent_executor = None
        self.is_initialized = False
        
        # 记忆管理
        self.chat_memory = None
        self.agent_with_memory = None
        if enable_memory:
            self._init_memory(memory_config or {})
    
    async def initialize(self):
        """初始化Agent"""
        if self.is_initialized:
            return
        
        try:
            logger.info("开始初始化智谱AI Agent...")
            
            # 1. 创建LLM（使用配置文件参数）
            await self._create_llm()
            
            # 2. 收集工具
            self._collect_tools()
            
            # 3. 加载MCP工具
            await self._load_mcp_tools()
            
            # 4. 构建Agent（使用外置模板系统）
            self._build_agent()
            
            # 5. 创建带记忆的Agent（如果启用记忆）
            if self.enable_memory and self.chat_memory:
                self._build_agent_with_memory()
            
            self.is_initialized = True
            logger.info(f"智谱AI Agent初始化完成 - 模型: {self.model}, 工具数量: {len(self.tools)}")
            
        except Exception as e:
            logger.error(f"Agent初始化失败: {e}")
            raise
    
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
        """获取模型配置"""
        try:
            model_info = get_llm_info("zhipu", self.model)
            
            # 从合并后的mode_defaults中提取温度设置
            mode_defaults = model_info.get("mode_defaults", {})
            llm_defaults = mode_defaults.get("llm", {})
            agent_defaults = mode_defaults.get("agent", {})
            
            # 优先使用llm模式的温度设置，然后是agent模式
            temperature = llm_defaults.get("temperature") or agent_defaults.get("temperature")
            
            if temperature is not None:
                model_info["temperature"] = temperature
                logger.info(f"从配置文件获取温度设置: {temperature}")
            
            return model_info
        except Exception as e:
            logger.warning(f"获取模型配置失败: {e}，使用默认配置")
            return {"max_tokens": 2048, "context_window": 128000}
    
    def _init_memory(self, config: Dict[str, Any]) -> None:
        """初始化记忆管理器"""
        try:
            if self.global_memory_manager:
                self.chat_memory = self.global_memory_manager
                logger.info("使用全局记忆管理器")
            else:
                self.chat_memory = GlobalMemoryManager(
                    storage_dir=config.get("storage_path", "data/sessions"),
                    max_messages=config.get("max_messages", 50)
                )
                logger.info("使用本地记忆管理器")
        except Exception as e:
            logger.error(f"记忆管理器初始化失败: {e}")
            self.enable_memory = False
    
    def _collect_tools(self):
        """收集核心工具"""
        self.tools = []
        
        # 基础工具：数学计算
        self.tools.extend([add_numbers, calculate_math])
        logger.info(f"已加载数学工具: {len([add_numbers, calculate_math])} 个")
        
        # 搜索工具：优先使用Tavily
        tavily_tools = get_available_tavily_tools()
        if tavily_tools:
            self.tools.extend(tavily_tools)
            logger.info(f"已加载Tavily搜索工具: {len(tavily_tools)} 个")
        
        # 地图工具
        amap_tools = get_available_amap_tools()
        if amap_tools:
            self.tools.extend(amap_tools)
            logger.info(f"已加载高德地图工具: {len(amap_tools)} 个")
        
        # 时间工具
        time_tools = get_available_time_tools()
        if time_tools:
            self.tools.extend(time_tools)
            logger.info(f"已加载时间工具: {len(time_tools)} 个")
        
        logger.info(f"核心工具收集完成，共 {len(self.tools)} 个")
    
    async def _load_mcp_tools(self):
        """加载MCP工具"""
        try:
            from ..MCP import GlobalMCPManager
            await GlobalMCPManager.initialize()
            mcp_tools = GlobalMCPManager.get_tools()
            if mcp_tools:
                self.tools.extend(mcp_tools)
                logger.info(f"MCP工具已加载: {len(mcp_tools)} 个")
        except Exception as e:
            logger.warning(f"MCP工具加载失败: {e}")
    
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
    
    def _build_agent_with_memory(self):
        """构建带记忆的Agent执行器"""
        try:
            if not self.agent_executor:
                raise ValueError("基础Agent必须先初始化")
            
            if self.global_memory_manager:
                self.agent_with_memory = self.global_memory_manager.create_runnable_with_memory(
                    self.agent_executor,
                    input_key="input",
                    history_key="chat_history"
                )
            else:
                self.agent_with_memory = self.chat_memory.create_runnable_with_memory(
                    self.agent_executor
                )
            
            logger.info("带记忆的Agent执行器创建完成")
            
        except Exception as e:
            logger.error(f"带记忆的Agent构建失败: {e}")
            self.enable_memory = False
            raise
    
    async def _execute_query(self, query: str, session_id: str = "default", **kwargs) -> Dict[str, Any]:
        """执行查询的核心逻辑"""
        try:
            # 使用带记忆的Agent（如果启用记忆）
            if self.enable_memory and self.agent_with_memory:
                result = await self.agent_with_memory.ainvoke(
                    {"input": query},
                    config={"configurable": {"session_id": session_id}}
                )
                
                # 保存会话
                if self.chat_memory:
                    self.chat_memory.save_session(session_id)
                
                # 提取工具名称
                tool_names = self._extract_tool_names(result.get("intermediate_steps", []))
                
                return {
                    "output": result["output"],
                    "intermediate_steps": result.get("intermediate_steps", []),
                    "success": True,
                    "tool_calls": len(result.get("intermediate_steps", [])),
                    "tool_names": tool_names,
                    "session_id": session_id,
                    "memory_enabled": True
                }
            else:
                # 使用无记忆的Agent
                result = await self.agent_executor.ainvoke({"input": query})
                
                # 提取工具名称
                tool_names = self._extract_tool_names(result.get("intermediate_steps", []))
                
                return {
                    "output": result["output"],
                    "intermediate_steps": result.get("intermediate_steps", []),
                    "success": True,
                    "tool_calls": len(result.get("intermediate_steps", [])),
                    "tool_names": tool_names,
                    "session_id": None,
                    "memory_enabled": False
                }
            
        except Exception as e:
            logger.error(f"查询处理失败: {e}")
            return {
                "output": f"查询处理失败: {str(e)}",
                "intermediate_steps": [],
                "success": False,
                "tool_calls": 0,
                "tool_names": [],
                "session_id": session_id,
                "memory_enabled": self.enable_memory
            }
    
    def _extract_tool_names(self, intermediate_steps: List) -> List[str]:
        """从中间步骤中提取工具名称"""
        tool_names = []
        for step in intermediate_steps:
            if hasattr(step, '__len__') and len(step) >= 1:
                # step 是 (AgentAction, observation) 元组
                agent_action = step[0]
                if hasattr(agent_action, 'tool'):
                    tool_names.append(agent_action.tool)
        return tool_names
    
    async def invoke(self, query: str, session_id: str = "default", **kwargs) -> Dict[str, Any]:
        """异步执行查询（主要接口）"""
        if not self.is_initialized:
            await self.initialize()
        
        return await self._execute_query(query, session_id, **kwargs)
    
    async def ainvoke(self, query: str, session_id: str = "default", **kwargs) -> Dict[str, Any]:
        """异步调用Agent（LangChain标准接口）"""
        return await self.invoke(query, session_id, **kwargs)
    
    def invoke_sync(self, query: str, session_id: str = "default") -> Dict[str, Any]:
        """同步执行查询（兼容旧接口）"""
        try:
            loop = asyncio.get_running_loop()
            task = asyncio.create_task(self.invoke(query, session_id))
            return asyncio.run_coroutine_threadsafe(task, loop).result()
        except RuntimeError:
            return asyncio.run(self.invoke(query, session_id))
    
    def get_agent_info(self) -> Dict[str, Any]:
        """获取Agent信息"""
        # 获取模型信息
        try:
            model_info = get_llm_info("zhipu", self.model)
        except Exception as e:
            logger.warning(f"Failed to get model info: {e}")
            model_info = {}
        
        # 获取实际使用的温度设置
        actual_temperature = self.temperature
        if hasattr(self, 'llm') and self.llm and hasattr(self.llm, 'temperature'):
            actual_temperature = self.llm.temperature
        
        info = {
            "provider": "zhipu",
            "model": self.model,
            "temperature": actual_temperature,
            "max_iterations": self.max_iterations,
            "initialized": self.is_initialized,
            "tool_count": len(self.tools),
            "tools": [tool.name for tool in self.tools] if self.tools else [],
            "memory_enabled": self.enable_memory,
            **model_info
        }
        
        # 添加记忆信息
        if self.enable_memory and self.chat_memory:
            info["memory_info"] = self.chat_memory.get_memory_stats()
        
        return info
    
    def get_info(self) -> Dict[str, Any]:
        """获取Agent信息(兼容旧接口)"""
        return self.get_agent_info()
    
    def get_llm(self):
        """获取底层LLM实例"""
        return self.llm
    
    def list_tools(self) -> List[str]:
        """列出工具名称"""
        return [tool.name for tool in self.tools]
    
    # 记忆管理方法
    def get_memory_stats(self) -> Optional[Dict[str, Any]]:
        """获取记忆统计信息"""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.get_memory_stats()
        return None
    
    def clear_memory(self, session_id: str = "default") -> bool:
        """清空指定会话记忆"""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.clear_session(session_id)
        return False
    
    def save_memory(self, session_id: str = "default") -> bool:
        """手动保存记忆"""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.save_session(session_id)
        return False
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话"""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.list_sessions()
        return []
    
    def delete_session(self, session_id: str) -> bool:
        """删除指定会话"""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.delete_session(session_id)
        return False
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话详细信息"""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.get_session_info(session_id)
        return None


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