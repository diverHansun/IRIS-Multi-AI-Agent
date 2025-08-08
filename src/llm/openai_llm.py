"""
OpenAI LLM Integration

提供OpenAI GPT模型的LangChain兼容包装器
支持GPT-4o和GPT-4o-mini模型
"""

import logging
from typing import Dict, Any, Optional, List, AsyncGenerator
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

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
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str = None, streaming: bool = False, **kwargs):
        """
        初始化OpenAI LLM
        
        Args:
            api_key: OpenAI API密钥
            model: 模型名称
            base_url: 自定义API端点URL (可选)
            streaming: 是否启用流式输出
            **kwargs: 其他LangChain ChatOpenAI参数
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.streaming = streaming
        self.kwargs = kwargs
        
        # 验证模型支持
        if model not in self.SUPPORTED_MODELS:
            logger.warning(f"模型 {model} 不在支持列表中，但仍会尝试使用")
        
        # 设置默认参数
        default_params = {
            "temperature": 0.1,
            "max_tokens": self.SUPPORTED_MODELS.get(model, {}).get("max_tokens", 4096),
            "timeout": 60,
            "max_retries": 3,
            "streaming": streaming
        }
        default_params.update(kwargs)
        self.llm_params = default_params
        
        logger.info(f"初始化OpenAI LLM: {model}")
    
    def create_llm(self) -> BaseChatModel:
        """创建LangChain ChatOpenAI实例"""
        try:
            llm_params = {
                "model": self.model,
                "openai_api_key": self.api_key,
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
    
    async def astream(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        异步流式调用模型
        
        Args:
            prompt: 输入提示
            
        Yields:
            生成的文本片段
        """
        try:
            # 创建LLM实例（如果还没有）
            llm = self.create_llm()
            
            # 确保消息格式正确
            message = HumanMessage(content=prompt) if isinstance(prompt, str) else prompt
            
            async for chunk in llm.astream([message]):
                if hasattr(chunk, 'content') and chunk.content:
                    yield chunk.content
                    
        except Exception as e:
            logger.error(f"OpenAI流式调用失败: {e}")
            yield f"流式调用错误: {str(e)}"


def build_openai_chat(
    api_key: str,
    model: str = "gpt-4o-mini", 
    temperature: float = 0.1,
    base_url: str = None,
    streaming: bool = False,
    **kwargs
) -> BaseChatModel:
    """
    构建OpenAI聊天模型
    
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