"""
Ollama LLM 封装

提供Ollama本地模型的统一接口，支持多种开源模型
基于 langchain-ollama 实现，兼容现有架构，支持function calling
"""

import logging
import asyncio
import aiohttp
import json
from typing import Dict, Any, Optional, List

from langchain_ollama import ChatOllama
from langchain_core.language_models import BaseChatModel

from ..config import settings

logger = logging.getLogger(__name__)


class OllamaLLM:
    """Ollama本地模型封装类"""
    
    
    def __init__(
        self,
        model: str = None,
        base_url: str = None,
        temperature: float = None,
        top_p: float = None,
        top_k: int = None,
        num_ctx: int = None,
        timeout: int = None,
        keep_alive: str = None,
        **kwargs
    ):
        """
        初始化Ollama LLM
        
        Args:
            model: 模型名称
            base_url: Ollama服务地址
            temperature: 采样温度
            top_p: 核采样参数
            top_k: top-k采样参数
            num_ctx: 上下文窗口大小
            timeout: 请求超时时间
            keep_alive: 模型保活时间
        """
        self.model = model or getattr(settings, 'default_ollama_model', 'gpt-oss:20b')
        self.base_url = base_url or settings.ollama_base_url
        self.timeout = timeout or settings.ollama_timeout
        self.keep_alive = keep_alive or settings.ollama_keep_alive
        
        # 从配置文件获取模型参数
        model_config = self._get_model_config(self.model)
        recommended_params = model_config.get("parameters", {})
        
        # 参数优先级：显式传入 > 模型推荐 > 全局默认
        self.temperature = temperature if temperature is not None else recommended_params.get("temperature", 0.1)
        self.top_p = top_p if top_p is not None else recommended_params.get("top_p", 0.8)
        self.top_k = top_k if top_k is not None else recommended_params.get("top_k", 40)
        self.num_ctx = num_ctx if num_ctx is not None else recommended_params.get("num_ctx", 32768)
        self.max_tokens = model_config.get('max_tokens', 8192)
        self.context_window = model_config.get('context_window', self.num_ctx)
        
        self.extra_kwargs = kwargs
        self._llm = None
        self._is_initialized = False
        
        logger.info(f"初始化Ollama LLM: {self.model} @ {self.base_url}")
    
    def _get_model_config(self, model: str) -> Dict[str, Any]:
        """获取模型的默认配置"""
        # Ollama模型配置基于模型名称的启发式推断
        config = {
            "description": f"Ollama {model} 本地模型",
            "supports_tools": True,  # 大部分现代模型都支持工具调用
            "parameters": {
                "temperature": 0.1,
                "top_p": 0.9,
                "top_k": 40,
                "num_ctx": 32768  # 默认上下文长度
            }
        }
        
        # 根据模型名称推断一些参数
        model_lower = model.lower()
        
        # 设置max_tokens和context_window
        if any(x in model_lower for x in ['20b', '32b', '70b']):
            # 大模型，更大的输出能力
            config["max_tokens"] = 8192
            config["context_window"] = 32768
        elif any(x in model_lower for x in ['1.5b', '3b', '7b', '8b']):
            # 中等模型
            config["max_tokens"] = 4096
            config["context_window"] = 16384
        else:
            # 默认配置
            config["max_tokens"] = 4096
            config["context_window"] = 16384
        
        # 特定模型的特殊配置
        if 'qwen' in model_lower:
            config["parameters"]["top_p"] = 0.8  # Qwen模型推荐配置
        elif 'deepseek' in model_lower:
            config["parameters"]["top_k"] = 50  # DeepSeek模型推荐配置
        
        return config
    
    async def health_check(self) -> bool:
        """
        检查Ollama服务健康状态
        
        Returns:
            bool: 服务是否可用
        """
        try:
            async with aiohttp.ClientSession() as session:
                # 检查服务状态
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [model["name"] for model in data.get("models", [])]
                        logger.info(f"Ollama服务正常，可用模型: {models}")
                        
                        # 检查目标模型是否已安装
                        if self.model in models:
                            logger.info(f"模型 {self.model} 已安装")
                            return True
                        else:
                            logger.warning(f"模型 {self.model} 未安装，尝试自动切换到可用模型...")
                          
                            available_tool_models = models[:3]  # 取前3个模型作为候选
                            if available_tool_models:
                                self.model = available_tool_models[0]
                                logger.info(f"自动切换到模型: {self.model}")
                                return True
                            else:
                                # 如果没有支持工具调用的模型，使用第一个可用模型
                                if models:
                                    self.model = models[0]
                                    logger.info(f"使用第一个可用模型: {self.model}")
                                    return True
                                else:
                                    logger.error("没有可用的模型")
                                    return False
                    else:
                        logger.error(f"Ollama服务异常，状态码: {response.status}")
                        return False
                        
        except asyncio.TimeoutError:
            logger.error("Ollama服务连接超时")
            return False
        except Exception as e:
            logger.error(f"Ollama健康检查失败: {str(e)}")
            return False
    
    async def pull_model_if_needed(self) -> bool:
        """
        如果模型不存在则尝试拉取
        
        Returns:
            bool: 模型是否可用
        """
        if await self.health_check():
            return True
            
        logger.info(f"尝试拉取模型 {self.model}...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/pull",
                    json={"name": self.model},
                    timeout=aiohttp.ClientTimeout(total=300)  # 拉取模型需要较长时间
                ) as response:
                    if response.status == 200:
                        logger.info(f"模型 {self.model} 拉取成功")
                        return True
                    else:
                        logger.error(f"模型拉取失败，状态码: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"模型拉取异常: {str(e)}")
            return False
    
    async def initialize(self) -> bool:
        """
        异步初始化Ollama LLM
        
        Returns:
            bool: 初始化是否成功
        """
        if self._is_initialized:
            return True
            
        try:
            # 检查服务健康状态
            logger.info(f"[DEBUG] 开始初始化OllamaLLM - 模型: {self.model}")
            logger.info(f"[DEBUG] 配置 - base_url: {self.base_url}")
            logger.info(f"[DEBUG] 配置 - timeout: {self.timeout}")
            logger.info(f"[DEBUG] 配置 - temperature: {self.temperature}")
            
            if not await self.health_check():
                logger.warning("Ollama服务不可用，尝试基本初始化")
                # 即使服务不可用也创建实例，运行时再报错
            
            # 创建ChatOllama实例
            logger.info(f"[DEBUG] 创建ChatOllama实例，request_timeout={float(self.timeout)}")
            
            # 创建ChatOllama实例
            # 注意: 不再强制禁用代理，依靠用户的代理配置（如Clash规则代理）处理网络路由
            self._llm = ChatOllama(
                model=self.model,
                base_url=self.base_url,
                temperature=self.temperature,
                top_p=self.top_p,
                top_k=self.top_k,
                num_ctx=self.num_ctx,
                keep_alive=self.keep_alive,
                timeout=self.timeout,
                request_timeout=float(self.timeout),
                **self.extra_kwargs
            )
            logger.info("[DEBUG] ✓ 创建ChatOllama实例成功")
            
            self._is_initialized = True
            logger.info(f"Ollama LLM 初始化成功: {self.model}")
            return True
            
        except Exception as e:
            logger.error(f"Ollama LLM 初始化失败: {str(e)}")
            return False
    
    def create_llm(self) -> BaseChatModel:
        """
        创建LangChain兼容的LLM实例
        
        Returns:
            BaseChatModel: LangChain聊天模型实例
        """
        if not self._is_initialized:
            # 检查是否在异步上下文中
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
                
            if loop is not None:
                # 在异步上下文中，同步调用健康检查
                logger.warning("在异步上下文中同步创建LLM，尝试同步健康检查...")
                
                # 使用requests进行同步健康检查
                try:
                    import requests
                    response = requests.get(f"{self.base_url}/api/tags", timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        models = [model["name"] for model in data.get("models", [])]
                        logger.info(f"同步健康检查通过，可用模型: {models}")
                        
                        # 检查并切换模型
                        if self.model not in models:
                            logger.warning(f"模型 {self.model} 未安装，尝试自动切换...")
                            # 假设大部分现代模型都支持工具调用
                            available_tool_models = models[:3]  # 取前3个模型作为候选
                            if available_tool_models:
                                self.model = available_tool_models[0]
                                logger.info(f"自动切换到模型: {self.model}")
                            elif models:
                                self.model = models[0]
                                logger.info(f"使用第一个可用模型: {self.model}")
                except Exception as e:
                    logger.warning(f"同步健康检查失败，继续创建: {e}")
            
            # 创建ChatOllama实例
            # 注意: 不再强制禁用代理，依靠用户的代理配置处理网络路由
            self._llm = ChatOllama(
                model=self.model,
                base_url=self.base_url,
                temperature=self.temperature,
                top_p=self.top_p,
                top_k=self.top_k,
                num_ctx=self.num_ctx,
                keep_alive=self.keep_alive,
                timeout=self.timeout,
                request_timeout=float(self.timeout),
                **self.extra_kwargs
            )
            logger.info("[DEBUG] ✓ 同步创建ChatOllama实例成功")
            
            self._is_initialized = True
            logger.info(f"Ollama LLM 创建完成: {self.model}")
        
        return self._llm
    
    def supports_tools(self) -> bool:
        """
        检查当前模型是否支持工具调用
        
        Returns:
            bool: 是否支持工具调用
        """
        model_config = self._get_model_config(self.model)
        return model_config.get("supports_tools", False)
    
    def bind_tools_if_supported(self, tools: List = None):
        """
        如果模型支持工具调用，则绑定工具
        
        Args:
            tools: 工具列表
            
        Returns:
            绑定工具后的LLM实例或原实例
        """
        if not self._llm:
            raise RuntimeError("LLM未初始化，请先调用create_llm()")
        
        if tools and self.supports_tools():
            logger.info(f"模型 {self.model} 支持工具调用，绑定 {len(tools)} 个工具")
            try:
                # 使用LangChain的bind_tools方法
                return self._llm.bind_tools(tools)
            except Exception as e:
                logger.warning(f"工具绑定失败，使用原始LLM: {str(e)}")
                return self._llm
        else:
            if tools:
                logger.info(f"模型 {self.model} 不支持原生工具调用，将使用ReAct模式")
            return self._llm
    
    
    
    @classmethod
    def get_supported_models(cls) -> Dict[str, Dict[str, Any]]:
        """
        动态获取本地已安装的Ollama模型列表
        
        Returns:
            Dict: 本地已安装的模型配置
        """
        try:
            import aiohttp
            import asyncio
            from ..config import settings
            
            async def fetch_local_models():
                base_url = settings.ollama_base_url
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{base_url}/api/tags", timeout=10) as response:
                            if response.status == 200:
                                data = await response.json()
                                models = {}
                                for model_info in data.get("models", []):
                                    model_name = model_info["name"]
                                    # 创建一个临时实例来获取配置
                                    temp_llm = cls(model=model_name)
                                    model_config = temp_llm._get_model_config(model_name)
                                    
                                    models[model_name] = {
                                        "name": model_name,
                                        "description": model_config["description"],
                                        "supports_tools": model_config["supports_tools"],
                                        "max_tokens": model_config["max_tokens"],
                                        "context_window": model_config["context_window"],
                                        "parameters": model_config["parameters"],
                                        "size": model_info.get("size", "Unknown"),
                                        "modified_at": model_info.get("modified_at", "Unknown")
                                    }
                                return models
                except Exception as e:
                    logger.error(f"获取本地模型失败: {e}")
                    return {}
            
            # 尝试在当前事件循环中运行
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果在异步上下文中，创建新的线程来运行
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, fetch_local_models())
                        return future.result(timeout=10)
                else:
                    return loop.run_until_complete(fetch_local_models())
            except RuntimeError:
                # 如果没有事件循环，创建新的
                return asyncio.run(fetch_local_models())
                
        except Exception as e:
            logger.warning(f"动态获取本地模型失败: {e}")
            return {}
    
    @classmethod
    def validate_model(cls, model: str) -> bool:
        """
        验证模型是否在本地已安装
        
        Args:
            model: 模型名称
            
        Returns:
            bool: 是否已安装
        """
        try:
            supported_models = cls.get_supported_models()
            return model in supported_models
        except:
            return False