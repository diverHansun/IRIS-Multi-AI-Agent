"""
智谱AI语言模型封装模块

提供智谱AI模型的LangChain兼容封装，支持流式输出。
"""

from langchain_community.chat_models import ChatZhipuAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, BaseMessage
from typing import AsyncGenerator, Optional, Callable, List, Union
from src.config import settings
# 移除不存在的导入
import os
import logging

logger = logging.getLogger(__name__)

class ZhipuAILLM:
    """智谱AI语言模型封装类，支持GLM-4.5/GLM-4.5-Flash系列特性"""
    
    def __init__(self, 
                 model: str = "glm-4-plus",
                 temperature: float = 0.1,
                 max_tokens: int = 2048,
                 api_key: str = None,
                 streaming: bool = False,
                 thinking_mode: bool = False,  # GLM-4.5思考模式
                 callback_manager: Optional[Callable] = None,
                 **kwargs):
        """
        初始化智谱AI模型
        
        Args:
            model: 模型名称，默认为glm-4-plus
            temperature: 温度参数，控制输出的随机性
            max_tokens: 最大输出token数
            api_key: API密钥，为None时使用配置中的密钥
            streaming: 是否启用流式输出
            thinking_mode: GLM-4.5思考模式，启用复杂推理和工具使用
            callback_manager: 回调管理器
            **kwargs: 其他参数
        """
        # 确定API密钥
        if not api_key:
            api_key = settings.zhipu_api_key
        
        if not api_key:
            raise ValueError("未找到ZHIPU_API_KEY，请检查配置")
        
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.streaming = streaming
        self.thinking_mode = thinking_mode
        self.llm = None  # 添加 llm 属性
        
        # GLM-4.5/GLM-4.5-Flash优化配置
        if model in ["glm-4.5", "glm-4.5-flash"]:
            # 为GLM-4.5系列设置更大的默认max_tokens
            if max_tokens == 2048:  # 如果是默认值，则优化
                if model == "glm-4.5-flash":
                    self.max_tokens = 96000  # GLM-4.5-Flash支持96K输出
                else:
                    self.max_tokens = 8192  # GLM-4.5默认更大的输出
            # GLM-4.5系列自动启用思考模式以获得更好的推理效果
            if not thinking_mode and 'thinking_mode' not in kwargs:
                self.thinking_mode = True
                logger.info(f"{model}自动启用思考模式以获得更好的推理效果")
        
        # 设置环境变量（备用）
        os.environ["ZHIPU_API_KEY"] = api_key
        
        # 注意: 不再强制删除代理设置，由用户的代理配置决定网络路由
        
        # 为GLM-4.5系列准备特殊参数
        llm_kwargs = kwargs.copy()
        if model in ["glm-4.5", "glm-4.5-flash"] and self.thinking_mode:
            # GLM-4.5思考模式相关参数 - 注意：具体参数名可能需要根据langchain-community的实现调整
            llm_kwargs.update({
                "thinking": True,  # 尝试思考模式参数
                "request_timeout": 120,  # 思考模式可能需要更长时间
                "do_sample": True,  # 启用采样以获得更好的创造性
            })
            
        # 存储LLM配置，延迟初始化
        self._llm_kwargs = llm_kwargs
    
    async def initialize(self):
        """初始化LLM实例"""
        if self.llm is None:
            self.llm = await self._initialize_llm()
        
    async def _initialize_llm(self) -> BaseChatModel:
        """初始化具体的LLM实例"""
        # 创建智谱AI模型实例，直接传递API密钥
        return ChatZhipuAI(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            zhipuai_api_key=self.api_key,
            streaming=self.streaming,  # 支持流式输出
            **self._llm_kwargs
        )
    
    def _validate_config(self) -> bool:
        """验证配置参数"""
        if not self.api_key:
            return False
        
        # 基本格式验证（智谱AI密钥通常以特定格式开头）
        if not isinstance(self.api_key, str) or len(self.api_key.strip()) < 10:
            return False
        
        return True
    
    def get_llm(self) -> BaseChatModel:
        """获取LangChain兼容的LLM实例（兼容旧接口）"""
        return self.llm
    
    def create_llm(self) -> BaseChatModel:
        """创建LangChain兼容的LLM实例（兼容旧接口）"""
        return self.llm