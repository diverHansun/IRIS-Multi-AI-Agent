"""
流式输出工具模块

提供LLM流式输出的统一接口和管理功能
支持智谱AI和OpenAI的流式调用
"""

import asyncio
import logging
import time
from typing import AsyncGenerator, Dict, Any, Optional, Union, Callable
from abc import ABC, abstractmethod
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.callbacks import AsyncCallbackHandler, BaseCallbackHandler

# 导入配置
try:
    from ...config import settings
except ImportError:
    # 如果作为独立模块运行，创建一个简单的配置
    class Settings:
        streaming_display_refresh_rate = 10
        streaming_delay_ms = 50
    settings = Settings()

logger = logging.getLogger(__name__)
console = Console()

class StreamingCallbackHandler(AsyncCallbackHandler):
    """流式输出回调处理器"""
    
    def __init__(self, on_token: Optional[Callable[[str], None]] = None):
        """
        初始化流式回调处理器
        
        Args:
            on_token: 接收到新token时的回调函数
        """
        self.on_token = on_token
        self.tokens = []
        self.current_text = ""
    
    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        """处理新的token"""
        try:
            self.tokens.append(token)
            self.current_text += token
            
            if self.on_token:
                self.on_token(token)
        except Exception as e:
            logger.error(f"流式回调处理失败: {e}")
    
    def get_full_text(self) -> str:
        """获取完整文本"""
        return self.current_text
    
    def clear(self):
        """清除累积的文本"""
        self.tokens.clear()
        self.current_text = ""

class StreamingDisplay:
    """流式显示管理器"""
    
    def __init__(self, title: str = "AI 回复"):
        """
        初始化流式显示
        
        Args:
            title: 显示面板标题
        """
        self.title = title
        self.content = ""
        self.live = None
        self.console = Console()
    
    def start(self):
        """开始流式显示"""
        try:
            self.live = Live(
                self._create_panel(),
                console=self.console,
                refresh_per_second=settings.streaming_display_refresh_rate,
                transient=False
            )
            self.live.start()
        except Exception as e:
            logger.error(f"启动流式显示失败: {e}")
    
    def update(self, new_content: str):
        """更新显示内容"""
        try:
            self.content += new_content
            if self.live:
                self.live.update(self._create_panel())
        except Exception as e:
            logger.error(f"更新流式显示失败: {e}")
    
    def stop(self):
        """停止流式显示"""
        try:
            if self.live:
                self.live.stop()
                self.live = None
        except Exception as e:
            logger.error(f"停止流式显示失败: {e}")
    
    def _create_panel(self) -> Panel:
        """创建显示面板"""
        # 添加光标效果
        display_content = self.content + "▊"
        
        return Panel(
            Text(display_content, style="green"),
            title=f"[bold cyan]{self.title}[/]",
            border_style="cyan",
            padding=(1, 2)
        )
    
    def get_content(self) -> str:
        """获取当前内容"""
        return self.content

class StreamingLLM(ABC):
    """流式LLM抽象基类"""
    
    @abstractmethod
    async def stream_generate(
        self, 
        prompt: str, 
        on_token: Optional[Callable[[str], None]] = None
    ) -> AsyncGenerator[str, None]:
        """
        流式生成文本
        
        Args:
            prompt: 输入提示
            on_token: token回调函数
            
        Yields:
            生成的文本片段
        """
        pass

class ZhipuStreamingLLM(StreamingLLM):
    """智谱AI流式LLM实现"""
    
    def __init__(self, llm: BaseChatModel):
        """
        初始化智谱流式LLM
        
        Args:
            llm: LangChain ChatModel实例
        """
        self.llm = llm
    
    async def stream_generate(
        self, 
        prompt: str, 
        on_token: Optional[Callable[[str], None]] = None
    ) -> AsyncGenerator[str, None]:
        """实现智谱AI的流式生成"""
        try:
            # 创建流式回调处理器
            callback_handler = StreamingCallbackHandler(on_token)
            
            # 使用流式接口
            async for chunk in self.llm.astream(
                [HumanMessage(content=prompt)],
                config={"callbacks": [callback_handler]}
            ):
                if hasattr(chunk, 'content') and chunk.content:
                    yield chunk.content
                    
        except Exception as e:
            logger.error(f"智谱AI流式生成失败: {e}")
            yield f"流式生成错误: {str(e)}"

class OpenAIStreamingLLM(StreamingLLM):
    """OpenAI流式LLM实现"""
    
    def __init__(self, llm: BaseChatModel):
        """
        初始化OpenAI流式LLM
        
        Args:
            llm: LangChain ChatModel实例
        """
        self.llm = llm
    
    async def stream_generate(
        self, 
        prompt: str, 
        on_token: Optional[Callable[[str], None]] = None
    ) -> AsyncGenerator[str, None]:
        """实现OpenAI的流式生成"""
        try:
            # 创建流式回调处理器
            callback_handler = StreamingCallbackHandler(on_token)
            
            # 使用流式接口
            async for chunk in self.llm.astream(
                [HumanMessage(content=prompt)],
                config={"callbacks": [callback_handler]}
            ):
                if hasattr(chunk, 'content') and chunk.content:
                    yield chunk.content
                    
        except Exception as e:
            logger.error(f"OpenAI流式生成失败: {e}")
            yield f"流式生成错误: {str(e)}"

class OllamaStreamingLLM(StreamingLLM):
    """Ollama流式LLM实现"""
    
    def __init__(self, llm: BaseChatModel):
        """
        初始化Ollama流式LLM
        
        Args:
            llm: LangChain ChatModel实例
        """
        self.llm = llm
    
    async def stream_generate(
        self, 
        prompt: str, 
        on_token: Optional[Callable[[str], None]] = None
    ) -> AsyncGenerator[str, None]:
        """实现Ollama的流式生成"""
        try:
            # 调试输出
            logger.info(f"[DEBUG] OllamaStreamingLLM开始流式生成")
            logger.info(f"[DEBUG] 提示长度: {len(prompt)} 字符")
            logger.info(f"[DEBUG] 提示预览: {prompt[:200]}...")
            logger.info(f"[DEBUG] LLM类型: {type(self.llm)}")
            
            # 创建流式回调处理器
            callback_handler = StreamingCallbackHandler(on_token)
            
            # 使用流式接口 - 添加异步锁防止并发问题
            logger.info(f"[DEBUG] 开始调用self.llm.astream()")
            chunk_count = 0
            
            try:
                async for chunk in self.llm.astream(
                    [HumanMessage(content=prompt)],
                    config={"callbacks": [callback_handler]}
                ):
                    if hasattr(chunk, 'content') and chunk.content:
                        chunk_count += 1
                        logger.debug(f"[DEBUG] 收到chunk #{chunk_count}: {chunk.content[:50]}...")
                        yield chunk.content
                
                logger.info(f"[DEBUG] 流式生成完成，共 {chunk_count} 个chunks")
                
            except Exception as astream_e:
                logger.error(f"[DEBUG] astream调用异常: {type(astream_e).__name__}: {astream_e}")
                
                # 详细分析502错误并使用HTTP fallback
                if hasattr(astream_e, 'status_code') and astream_e.status_code == 502:
                    logger.error(f"[DEBUG] 502错误，启用HTTP fallback")
                    logger.error(f"[DEBUG]   LangChain异常: {type(astream_e).__name__}: {astream_e}")
                    
                    # 使用直接HTTP客户端作为fallback
                    try:
                        from .ollama_http_client import OllamaHttpClient
                        
                        base_url = getattr(self.llm, 'base_url', 'http://localhost:11434')
                        model = getattr(self.llm, 'model', 'unknown')
                        temperature = getattr(self.llm, 'temperature', 0.1)
                        
                        logger.error(f"[DEBUG] 使用HTTP fallback: {base_url}, 模型: {model}")
                        
                        http_client = OllamaHttpClient(base_url=base_url, timeout=300)
                        
                        chunk_count = 0
                        async for chunk in http_client.stream_chat(model, prompt, temperature):
                            chunk_count += 1
                            logger.debug(f"[DEBUG] HTTP fallback chunk #{chunk_count}: {chunk[:30]}...")
                            yield chunk
                        
                        logger.info(f"[DEBUG] HTTP fallback成功，共 {chunk_count} chunks")
                        return
                        
                    except Exception as http_e:
                        logger.error(f"[DEBUG] HTTP fallback也失败: {http_e}")
                        # 继续原有的fallback逻辑
                
                # 如果是并发问题，尝试使用同步方法作为fallback
                if "asynchronous generator is already running" in str(astream_e):
                    logger.warning(f"[DEBUG] 检测到异步生成器并发问题，尝试同步调用作为fallback")
                    
                    # 使用invoke作为fallback
                    try:
                        result = await self.llm.ainvoke([HumanMessage(content=prompt)])
                        if hasattr(result, 'content') and result.content:
                            # 将完整结果分块返回以模拟流式
                            content = result.content
                            chunk_size = max(1, len(content) // 10)  # 分成约10个块
                            for i in range(0, len(content), chunk_size):
                                chunk = content[i:i+chunk_size]
                                logger.debug(f"[DEBUG] Fallback chunk: {chunk[:30]}...")
                                yield chunk
                            return
                        else:
                            yield "Fallback response completed"
                            return
                    except Exception as fallback_e:
                        logger.error(f"[DEBUG] Fallback也失败: {fallback_e}")
                
                raise astream_e
                    
        except Exception as e:
            logger.error(f"[DEBUG] Ollama流式生成异常: {type(e).__name__}: {e}")
            if hasattr(e, 'status_code'):
                logger.error(f"[DEBUG] 状态码: {e.status_code}")
            if hasattr(e, 'response'):
                logger.error(f"[DEBUG] 响应内容: {e.response}")
            if hasattr(e, 'request'):
                logger.error(f"[DEBUG] 请求信息: {e.request}")
            
            # 添加更多调试信息
            logger.error(f"[DEBUG] 异常属性: {dir(e)}")
            logger.error(f"[DEBUG] LLM配置检查:")
            logger.error(f"[DEBUG]   model: {getattr(self.llm, 'model', 'Unknown')}")
            logger.error(f"[DEBUG]   base_url: {getattr(self.llm, 'base_url', 'Unknown')}")
            logger.error(f"[DEBUG]   timeout: {getattr(self.llm, 'timeout', 'Unknown')}")
            
            # 测试直接连接
            logger.error(f"[DEBUG] 测试直接Ollama连接...")
            try:
                import requests
                base_url = getattr(self.llm, 'base_url', 'http://localhost:11434')
                response = requests.get(f"{base_url}/api/tags", timeout=10)
                logger.error(f"[DEBUG] 直接连接状态: {response.status_code}")
            except Exception as conn_e:
                logger.error(f"[DEBUG] 直接连接失败: {conn_e}")
            
            yield f"流式生成错误: {str(e)}"

class StreamingManager:
    """流式输出管理器"""
    
    def __init__(self):
        """初始化流式管理器"""
        self.streaming_llms: Dict[str, StreamingLLM] = {}
    
    def register_llm(self, provider: str, llm: BaseChatModel):
        """
        注册流式LLM
        
        Args:
            provider: 提供商名称 (zhipu, openai, ollama)
            llm: LangChain ChatModel实例
        """
        try:
            if provider.lower() == "zhipu":
                self.streaming_llms[provider] = ZhipuStreamingLLM(llm)
            elif provider.lower() == "openai":
                self.streaming_llms[provider] = OpenAIStreamingLLM(llm)
            elif provider.lower() == "ollama":
                self.streaming_llms[provider] = OllamaStreamingLLM(llm)
            else:
                logger.warning(f"不支持的流式LLM提供商: {provider}")
                
            logger.info(f"注册流式LLM: {provider}")
        except Exception as e:
            logger.error(f"注册流式LLM失败 {provider}: {e}")
    
    async def stream_chat(
        self, 
        provider: str, 
        prompt: str,
        display_title: str = "AI 回复",
        show_display: bool = True
    ) -> Dict[str, Any]:
        """
        执行流式聊天
        
        Args:
            provider: LLM提供商
            prompt: 输入提示
            display_title: 显示标题
            show_display: 是否显示流式界面
            
        Returns:
            包含回复文本和性能指标的字典
        """
        if provider not in self.streaming_llms:
            raise ValueError(f"未注册的流式LLM提供商: {provider}")
        
        streaming_llm = self.streaming_llms[provider]
        full_response = ""
        start_time = time.time()
        chunk_count = 0
        
        # 初始化显示器
        display = None
        if show_display:
            display = StreamingDisplay(display_title)
            display.start()
        
        try:
            # 执行流式生成
            async for chunk in streaming_llm.stream_generate(prompt):
                full_response += chunk
                chunk_count += 1
                
                # 更新显示
                if display:
                    display.update(chunk)
                
                # 小延迟以提供更好的视觉效果
                await asyncio.sleep(settings.streaming_delay_ms / 1000.0)
                
        except Exception as e:
            error_msg = f"流式聊天失败: {str(e)}"
            logger.error(error_msg)
            full_response = error_msg
            
            # 如果是Unicode编码错误，不要误报为网络错误
            if "gbk" in str(e) and "can't encode" in str(e):
                logger.warning("[DEBUG] 检测到Unicode编码问题，这不是网络502错误")
                full_response = "响应成功，但显示时遇到编码问题"
            
        finally:
            # 停止显示
            if display:
                display.stop()
                
                # 计算性能指标
                elapsed = time.time() - start_time
                chars_per_second = len(full_response) / elapsed if elapsed > 0 else 0
                
                # 显示最终结果和性能指标 - 安全处理Unicode
                try:
                    console.print(Panel(
                        full_response,
                        title=f"[bold green]{display_title} (完成)[/]",
                        border_style="green"
                    ))
                except UnicodeEncodeError:
                    # 如果有Unicode问题，使用简化显示
                    print(f"\n=== {display_title} (完成) ===")
                    # 尝试安全编码
                    try:
                        safe_response = full_response.encode('gbk', errors='replace').decode('gbk')
                        print(safe_response)
                    except:
                        print("[响应内容包含特殊字符，无法完整显示]")
                    print("=" * 50)
                
                if chunk_count > 0:
                    try:
                        console.print(
                            f"[dim]⚡ 性能: {elapsed:.2f}s | "
                            f"{len(full_response)} 字符 | "
                            f"{chars_per_second:.1f} 字符/秒 | "
                            f"{chunk_count} 数据块[/]"
                        )
                    except UnicodeEncodeError:
                        # 安全的性能显示
                        print(f"性能: {elapsed:.2f}s | {len(full_response)} 字符 | {chars_per_second:.1f} 字符/秒 | {chunk_count} 数据块")
        
        return {
            "response": full_response,
            "elapsed_time": time.time() - start_time,
            "chunk_count": chunk_count,
            "characters": len(full_response),
            "success": not full_response.startswith("流式聊天失败")
        }
    
    def get_supported_providers(self) -> list:
        """获取支持的流式提供商列表"""
        return list(self.streaming_llms.keys())

# 全局流式管理器实例
streaming_manager = StreamingManager()

# 便捷函数
async def stream_llm_response(
    provider: str,
    prompt: str,
    llm: Optional[BaseChatModel] = None,
    display_title: str = "AI 回复",
    show_display: bool = True
) -> str:
    """
    便捷的流式LLM调用函数
    
    Args:
        provider: LLM提供商
        prompt: 输入提示
        llm: LangChain ChatModel实例 (可选，用于动态注册)
        display_title: 显示标题
        show_display: 是否显示流式界面
        
    Returns:
        完整的回复文本
    """
    # 动态注册LLM（如果提供）
    if llm and provider not in streaming_manager.get_supported_providers():
        streaming_manager.register_llm(provider, llm)
    
    result = await streaming_manager.stream_chat(
        provider=provider,
        prompt=prompt,
        display_title=display_title,
        show_display=show_display
    )
    
    return result["response"]

async def demo_streaming():
    """流式输出演示"""
    console.print("[bold blue]流式输出演示[/]")
    
    # 模拟流式输出
    demo_text = "这是一个流式输出的演示。我们可以看到文字逐字出现，就像真实的AI对话一样。这种效果可以大大提升用户体验，让用户感觉到AI正在实时思考和回应。"
    
    display = StreamingDisplay("演示")
    display.start()
    
    try:
        for char in demo_text:
            display.update(char)
            await asyncio.sleep(settings.streaming_delay_ms / 1000.0)  # 模拟打字效果
            
    finally:
        display.stop()
        console.print("[green]演示完成！[/]")

if __name__ == "__main__":
    # 运行演示
    asyncio.run(demo_streaming())