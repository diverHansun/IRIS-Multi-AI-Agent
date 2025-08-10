"""
OpenAI LLM Integration

提供OpenAI GPT模型的LangChain兼容包装器
支持GPT-4o和GPT-4o-mini模型
"""

import logging
from typing import Dict, Any, Optional, List, AsyncGenerator, Union
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, BaseMessage


logger = logging.getLogger(__name__)

class OpenAILLM:
    """OpenAI LLM包装器类"""
    
    # 支持的模型配置
    SUPPORTED_MODELS = {
        "gpt-4o": {
            "model_name": "gpt-4o",
            "max_tokens": 4096,
            "description": "GPT-4o - 最新的GPT-4优化版本，性能和成本平衡"
        },
        "gpt-4o-mini": {
            "model_name": "gpt-4o-mini",
            "max_tokens": 16384,
            "description": "GPT-4o-mini - 轻量级版本，速度快成本低"
        },
        "gpt-4-turbo": {
            "model_name": "gpt-4-turbo",
            "max_tokens": 4096,
            "description": "GPT-4 Turbo - 高性能版本"
        }
    }
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str = None, streaming: bool = False,
                 temperature: float = 0.1, max_tokens: int = 4096, callback_manager: Optional[Any] = None,
                 **kwargs):
        """
        初始化OpenAI LLM
        
        Args:
            api_key: OpenAI API密钥
            model: 模型名称
            base_url: 自定义API端点URL (可选)
            streaming: 是否启用流式输出
            temperature: 温度参数
            max_tokens: 最大输出令牌数
            callback_manager: 回调管理器
            **kwargs: 其他LangChain ChatOpenAI参数
        """
        # 初始化基类
        super().__init__(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            callback_manager=callback_manager,
            **kwargs
        )
        
        # 设置提供商信息
        self.provider_name = "OpenAI"
        self.api_key = api_key
        self.base_url = base_url
        
        # 验证模型支持
        if model not in self.SUPPORTED_MODELS:
            logger.warning(f"模型 {model} 不在支持列表中，但仍会尝试使用")
        
        # 设置默认参数
        self.llm_params = {
            "timeout": 60,
            "max_retries": 3,
        }
        self.llm_params.update(kwargs)
        
        logger.info(f"初始化OpenAI LLM: {model}")
    
    async def _initialize_llm(self) -> BaseChatModel:
        """初始化具体的LLM实例"""
        try:
            llm_params = {
                "model": self.model,
                "openai_api_key": self.api_key,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "streaming": self.streaming,
                **self.llm_params
            }
            
            # 如果提供了自定义base_url，则添加到参数中
            if self.base_url:
                llm_params["base_url"] = self.base_url
                logger.info(f"使用自定义OpenAI API端点: {self.base_url}")
            
            llm = ChatOpenAI(**llm_params)
            
            logger.info(f"成功创建OpenAI LLM实例: {self.model}")
            return llm
            
        except Exception as e:
            logger.error(f"创建OpenAI LLM失败: {str(e)}")
            raise
    
    def _validate_config(self) -> bool:
        """验证配置参数"""
        return self.validate_api_key(self.api_key)
    
    def create_llm(self) -> BaseChatModel:
        """创建LangChain ChatOpenAI实例（兼容旧接口）"""
        import asyncio
        
        # 如果在异步环境中，需要手动初始化
        try:
            loop = asyncio.get_running_loop()
            # 在异步环境中，返回延迟初始化的实例
            return self.llm  
        except RuntimeError:
            # 在同步环境中，使用事件循环初始化
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.initialize())
                return self.llm
            finally:
                loop.close()
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        model_config = self.SUPPORTED_MODELS.get(self.model, {})
        return {
            "provider": "openai",
            "model": self.model,
            "description": model_config.get("description", "OpenAI模型"),
            "max_tokens": model_config.get("max_tokens", 4096),
            "parameters": self.llm_params,
            "supported": self.model in self.SUPPORTED_MODELS
        }
    
    @classmethod
    def get_supported_models(cls) -> Dict[str, Dict[str, Any]]:
        """获取支持的模型列表"""
        return cls.SUPPORTED_MODELS.copy()
    
    @classmethod
    def validate_api_key(cls, api_key: str) -> bool:
        """验证API密钥格式"""
        if not api_key:
            return False
        
        # OpenAI API密钥通常以sk-开头
        if not api_key.startswith('sk-'):
            logger.warning("OpenAI API密钥格式可能不正确（通常以'sk-'开头）")
            return False
        
        # 检查长度（OpenAI API密钥通常较长）
        if len(api_key) < 20:
            logger.warning("OpenAI API密钥长度可能不正确")
            return False
        
        return True
    
    # 流式调用现在继承自基类BaseLLM.astream()


def build_openai_chat(
    api_key: str,
    model: str = "gpt-4o-mini", 
    temperature: float = 0.1,
    base_url: str = None,
    streaming: bool = False,
    **kwargs
) -> BaseChatModel:
    """
    构建OpenAI聊天模型（兼容旧接口）
    
    Args:
        api_key: OpenAI API密钥
        model: 模型名称
        temperature: 温度参数
        base_url: 自定义API端点URL (可选)
        streaming: 是否启用流式输出
        **kwargs: 其他参数
    
    Returns:
        LangChain ChatOpenAI实例
    """
    llm_wrapper = OpenAILLM(
        api_key=api_key,
        model=model,
        temperature=temperature,
        base_url=base_url,
        streaming=streaming,
        **kwargs
    )
    
    return llm_wrapper.create_llm()


async def create_openai_llm_async(
    api_key: str,
    model: str = "gpt-4o-mini", 
    temperature: float = 0.1,
    base_url: str = None,
    streaming: bool = False,
    **kwargs
) -> OpenAILLM:
    """
    异步创建OpenAI LLM实例
    
    Args:
        api_key: OpenAI API密钥
        model: 模型名称
        temperature: 温度参数
        base_url: 自定义API端点URL (可选)
        streaming: 是否启用流式输出
        **kwargs: 其他参数
    
    Returns:
        初始化完成的OpenAILLM实例
    """
    llm_wrapper = OpenAILLM(
        api_key=api_key,
        model=model,
        temperature=temperature,
        base_url=base_url,
        streaming=streaming,
        **kwargs
    )
    
    await llm_wrapper.initialize()
    return llm_wrapper


# 便捷函数
def create_gpt4o(api_key: str, **kwargs) -> BaseChatModel:
    """创建GPT-4o模型"""
    return build_openai_chat(api_key, model="gpt-4o", **kwargs)


def create_gpt4o_mini(api_key: str, **kwargs) -> BaseChatModel:
    """创建GPT-4o-mini模型"""
    return build_openai_chat(api_key, model="gpt-4o-mini", **kwargs)


def create_gpt4_turbo(api_key: str, **kwargs) -> BaseChatModel:
    """创建GPT-4-turbo模型"""
    return build_openai_chat(api_key, model="gpt-4-turbo", **kwargs)