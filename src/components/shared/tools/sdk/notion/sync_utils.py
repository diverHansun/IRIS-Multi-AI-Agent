"""
同步工具辅助模块

提供异步函数到同步函数的转换工具，解决事件循环冲突问题。
"""

import asyncio
import logging
import threading
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


def async_to_sync(async_func: Callable[..., Coroutine]) -> Callable[..., Any]:
    """
    将异步函数转换为同步函数的装饰器
    
    处理事件循环冲突问题：
    1. 如果没有事件循环，创建新的
    2. 如果事件循环正在运行，在新线程中运行
    3. 如果事件循环存在但未运行，直接使用
    
    Args:
        async_func: 异步函数
        
    Returns:
        同步包装函数
    """
    def sync_wrapper(*args, **kwargs):
        async def _async_wrapper():
            return await async_func(*args, **kwargs)
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                logger.debug("Event loop running; executing async function in thread")
                # 如果事件循环正在运行，使用新线程
                result = None
                exception = None
                
                def run_in_thread():
                    nonlocal result, exception
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        result = new_loop.run_until_complete(_async_wrapper())
                        new_loop.close()
                    except Exception as e:
                        exception = e
                        logger.error("Async execution failed in thread: %s", e, exc_info=True)
                    finally:
                        # 清理线程中的事件循环
                        try:
                            asyncio.set_event_loop(None)
                        except:
                            pass
                
                thread = threading.Thread(target=run_in_thread)
                thread.start()
                thread.join()
                
                if exception:
                    raise exception
                return result
            else:
                logger.debug("Event loop present and not running; executing directly")
                return loop.run_until_complete(_async_wrapper())
        except RuntimeError:
            # 没有事件循环，创建新的
            logger.debug("No event loop found; creating new loop for async function")
            return asyncio.run(_async_wrapper())
    
    return sync_wrapper


def run_async_safely(coro_func: Callable[[], Coroutine]) -> Any:
    """
    安全地运行协程函数，处理事件循环冲突
    
    Args:
        coro_func: 返回协程对象的函数
        
        Returns:
            协程执行结果
    """
    try:
        # 尝试获取当前的事件循环
        try:
            loop = asyncio.get_running_loop()
            # 如果有运行中的事件循环，在新线程中运行
            result = None
            exception = None
            
            def run_in_thread():
                nonlocal result, exception
                try:
                    new_loop = asyncio.new_event_loop()
                    # 创建新的协程对象避免重用
                    fresh_coro = coro_func()
                    result = new_loop.run_until_complete(fresh_coro)
                except Exception as e:
                    exception = e
                    logger.error("Coroutine failed in thread with running loop: %s", e, exc_info=True)
                finally:
                    try:
                        new_loop.close()
                    except:
                        pass
            
            logger.debug("Running coroutine in thread because loop is already running")
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()
            
            if exception:
                raise exception
            return result
            
        except RuntimeError:
            # 没有运行中的事件循环，尝试使用已存在的事件循环
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    logger.debug("Using existing but idle event loop to run coroutine")
                    fresh_coro = coro_func()
                    return loop.run_until_complete(fresh_coro)
                else:
                    # 如果这里还是运行中，在新线程中运行
                    raise RuntimeError("事件循环正在运行")
            except RuntimeError:
                # 没有事件循环，创建新的
                logger.debug("No existing event loop; creating new loop with asyncio.run")
                fresh_coro = coro_func()
                return asyncio.run(fresh_coro)
                
    except Exception as e:
        # 全部失败，在新线程中创建全新的事件循环
        result = None
        exception = None
        
        def run_in_thread():
            nonlocal result, exception
            try:
                fresh_coro = coro_func()
                result = asyncio.run(fresh_coro)
            except Exception as ex:
                exception = ex
                logger.error("Coroutine failed in fallback thread execution: %s", ex, exc_info=True)
        
        logger.debug("Running coroutine in fallback thread with new event loop")
        thread = threading.Thread(target=run_in_thread)
        thread.start()
        thread.join()
        
        if exception:
            raise exception
        return result
