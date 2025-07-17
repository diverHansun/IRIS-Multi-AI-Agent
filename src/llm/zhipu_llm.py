"""
智谱AI语言模型封装模块

提供智谱AI模型的LangChain兼容封装。
"""

from langchain_community.chat_models import ChatZhipuAI
from langchain_core.language_models.chat_models import BaseChatModel
from ..config import settings
import os

class ZhipuAILLM:
    """智谱AI语言模型封装类"""
    
    def __init__(self, 
                 model: str = "glm-4-plus",
                 temperature: float = 0.1,
                 max_tokens: int = 2048,
                 **kwargs):
        """
        初始化智谱AI模型
        
        Args:
            model: 模型名称，默认为glm-4
            temperature: 温度参数，控制输出的随机性
            max_tokens: 最大输出token数
            **kwargs: 其他参数
        """
        # 检查API密钥
        if not settings.zhipu_api_key:
            raise ValueError("未找到ZHIPU_API_KEY，请检查配置")
        
        # 设置环境变量（备用）
        os.environ["ZHIPU_API_KEY"] = settings.zhipu_api_key
        
        # 清除代理设置以避免连接问题
        os.environ.pop('HTTP_PROXY', None)
        os.environ.pop('HTTPS_PROXY', None)
        os.environ.pop('http_proxy', None)
        os.environ.pop('https_proxy', None)
        
        # 创建智谱AI模型实例，直接传递API密钥
        self.llm = ChatZhipuAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            zhipuai_api_key=settings.zhipu_api_key,  # 直接传递API密钥
            **kwargs
        )
    
    def get_llm(self) -> BaseChatModel:
        """获取LangChain兼容的LLM实例"""
        return self.llm
    
    def invoke(self, prompt: str) -> str:
        """
        同步调用模型
        
        Args:
            prompt: 输入提示
            
        Returns:
            模型输出文本
        """
        try:
            response = self.llm.invoke(prompt)
            return response.content
        except Exception as e:
            print(f"❌ 智谱AI调用失败: {e}")
            return f"调用错误: {str(e)}"
    
    async def ainvoke(self, prompt: str) -> str:
        """
        异步调用模型
        
        Args:
            prompt: 输入提示
            
        Returns:
            模型输出文本
        """
        try:
            response = await self.llm.ainvoke(prompt)
            return response.content
        except Exception as e:
            print(f"❌ 智谱AI异步调用失败: {e}")
            return f"异步调用错误: {str(e)}"

def create_zhipu_llm(model: str = "glm-4-plus", **kwargs) -> BaseChatModel:
    """
    创建智谱AI LLM实例的工厂函数
    
    Args:
        model: 模型名称
        **kwargs: 其他参数
        
    Returns:
        LangChain兼容的ChatModel实例
    """
    zhipu_llm = ZhipuAILLM(model=model, **kwargs)
    return zhipu_llm.get_llm() 