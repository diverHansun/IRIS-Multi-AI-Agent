"""
Notion页面操作工具

提供对Notion页面的读取和内容提取功能。
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union

from .client import NotionClient, create_notion_client
from .data_processor import NotionDataProcessor

logger = logging.getLogger(__name__)


class NotionPageTools:
    """Notion页面操作工具类"""
    
    def __init__(self, client: Optional[NotionClient] = None):
        """
        初始化页面工具
        
        Args:
            client: Notion客户端，如果不提供则创建默认客户端
        """
        self.client = client or create_notion_client()
        self.processor = NotionDataProcessor()
    
    async def get_page_info(self, page_id: str) -> Dict[str, Any]:
        """
        获取页面基本信息
        
        Args:
            page_id: 页面ID
            
        Returns:
            页面信息
        """
        try:
            logger.info(f"获取页面信息: {page_id}")
            raw_data = await self.client.get_page(page_id)
            
            # 处理页面基本信息
            info = {
                "id": raw_data.get("id"),
                "created_time": raw_data.get("created_time"),
                "last_edited_time": raw_data.get("last_edited_time"),
                "url": raw_data.get("url"),
                "archived": raw_data.get("archived", False),
                "properties": {}
            }
            
            # 处理页面属性
            properties = raw_data.get("properties", {})
            for prop_name, prop_data in properties.items():
                info["properties"][prop_name] = self.processor.process_property_value(
                    prop_name, prop_data
                )
            
            # 提取页面标题
            title = None
            for prop_name, prop_value in info["properties"].items():
                if isinstance(prop_value, str) and prop_value.strip():
                    title = prop_value
                    break
            
            info["title"] = title or "无标题页面"
            
            return info
            
        except Exception as e:
            logger.error(f"获取页面信息失败: {e}")
            raise
    
    async def get_page_content(self, page_id: str) -> Dict[str, Any]:
        """
        获取页面内容
        
        Args:
            page_id: 页面ID
            
        Returns:
            页面内容
        """
        try:
            logger.info(f"获取页面内容: {page_id}")
            raw_content = await self.client.get_page_content(page_id)
            
            return self.processor.process_page_content(raw_content)
            
        except Exception as e:
            logger.error(f"获取页面内容失败: {e}")
            raise
    
    async def get_page_full_content(self, page_id: str) -> Dict[str, Any]:
        """
        获取页面完整内容（包括嵌套块）
        
        Args:
            page_id: 页面ID
            
        Returns:
            完整页面内容
        """
        try:
            logger.info(f"获取页面完整内容: {page_id}")
            
            # 获取页面信息
            page_info = await self.get_page_info(page_id)
            
            # 获取页面内容
            page_content = await self.get_page_content(page_id)
            
            # 递归获取有子块的内容
            await self._process_nested_blocks(page_content["blocks"])
            
            return {
                "page_info": page_info,
                "content": page_content
            }
            
        except Exception as e:
            logger.error(f"获取页面完整内容失败: {e}")
            raise
    
    async def _process_nested_blocks(self, blocks: List[Dict[str, Any]]):
        """
        递归处理嵌套块
        
        Args:
            blocks: 块列表
        """
        for block in blocks:
            if block.get("has_children", False):
                try:
                    child_content = await self.client.get_block_children(block["id"])
                    child_blocks = self.processor.process_page_content(child_content)
                    block["children"] = child_blocks["blocks"]
                    
                    # 递归处理子块
                    await self._process_nested_blocks(block["children"])
                    
                except Exception as e:
                    logger.warning(f"获取子块内容失败 {block['id']}: {e}")
                    block["children"] = []
    
    async def get_page_text_summary(self, page_id: str) -> str:
        """
        获取页面文本摘要
        
        Args:
            page_id: 页面ID
            
        Returns:
            页面文本摘要
        """
        try:
            # 获取页面信息和内容
            page_info = await self.get_page_info(page_id)
            page_content = await self.get_page_content(page_id)
            
            # 构建摘要
            summary_parts = [
                f"页面标题: {page_info['title']}",
                f"创建时间: {page_info.get('created_time', 'unknown')}",
                f"最后编辑: {page_info.get('last_edited_time', 'unknown')}"
            ]
            
            # 添加属性信息
            if page_info["properties"]:
                summary_parts.append("\\n页面属性:")
                for prop_name, prop_value in page_info["properties"].items():
                    if prop_value and str(prop_value).strip():
                        summary_parts.append(f"- {prop_name}: {str(prop_value)[:100]}")
            
            # 添加内容摘要
            full_text = page_content.get("full_text", "")
            if full_text.strip():
                summary_parts.append("\\n页面内容:")
                # 限制文本长度
                content_preview = full_text[:500]
                if len(full_text) > 500:
                    content_preview += "..."
                summary_parts.append(content_preview)
            else:
                summary_parts.append("\\n页面内容: （空白页面）")
            
            summary_parts.append(f"\\n总块数: {page_content.get('total_blocks', 0)}")
            
            return "\\n".join(summary_parts)
            
        except Exception as e:
            logger.error(f"获取页面摘要失败: {e}")
            return f"获取页面摘要时出错: {str(e)}"
    
    async def search_page_content(self, page_id: str, search_text: str) -> Dict[str, Any]:
        """
        在页面内容中搜索文本
        
        Args:
            page_id: 页面ID
            search_text: 搜索文本
            
        Returns:
            搜索结果
        """
        try:
            logger.info(f"在页面中搜索: {page_id}, 搜索词: {search_text}")
            
            page_content = await self.get_page_content(page_id)
            search_text_lower = search_text.lower()
            
            matching_blocks = []
            full_text = page_content.get("full_text", "")
            
            # 在每个块中搜索
            for block in page_content["blocks"]:
                text_content = block.get("text_content", "")
                if search_text_lower in text_content.lower():
                    matching_blocks.append({
                        "block_id": block["id"],
                        "block_type": block["type"],
                        "text_content": text_content,
                        "match_context": self._extract_match_context(text_content, search_text)
                    })
            
            # 检查整体文本匹配
            full_text_matches = search_text_lower in full_text.lower()
            
            return {
                "page_id": page_id,
                "search_text": search_text,
                "matches_found": len(matching_blocks),
                "full_text_contains": full_text_matches,
                "matching_blocks": matching_blocks
            }
            
        except Exception as e:
            logger.error(f"搜索页面内容失败: {e}")
            raise
    
    def _extract_match_context(self, text: str, search_text: str, context_length: int = 100) -> str:
        """
        提取匹配文本的上下文
        
        Args:
            text: 原始文本
            search_text: 搜索文本
            context_length: 上下文长度
            
        Returns:
            包含匹配的上下文文本
        """
        text_lower = text.lower()
        search_lower = search_text.lower()
        
        match_index = text_lower.find(search_lower)
        if match_index == -1:
            return text[:context_length] + "..." if len(text) > context_length else text
        
        start = max(0, match_index - context_length // 2)
        end = min(len(text), match_index + len(search_text) + context_length // 2)
        
        context = text[start:end]
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."
        
        return context
    
    async def close(self):
        """关闭客户端连接"""
        await self.client.close()


# 同步包装函数，用于LangChain工具集成
def sync_get_page_info(page_id: str) -> Dict[str, Any]:
    """同步获取页面信息"""
    from .sync_utils import run_async_safely
    
    def _async_wrapper():
        async def _inner():
            tools = NotionPageTools()
            try:
                return await tools.get_page_info(page_id)
            finally:
                await tools.close()
        return _inner()
    
    return run_async_safely(_async_wrapper)


def sync_get_page_content(page_id: str) -> Dict[str, Any]:
    """同步获取页面内容"""
    from .sync_utils import run_async_safely
    
    def _async_wrapper():
        async def _inner():
            tools = NotionPageTools()
            try:
                return await tools.get_page_content(page_id)
            finally:
                await tools.close()
        return _inner()
    
    return run_async_safely(_async_wrapper)


def sync_get_page_full_content(page_id: str) -> Dict[str, Any]:
    """同步获取页面完整内容"""
    from .sync_utils import run_async_safely
    
    def _async_wrapper():
        async def _inner():
            tools = NotionPageTools()
            try:
                return await tools.get_page_full_content(page_id)
            finally:
                await tools.close()
        return _inner()
    
    return run_async_safely(_async_wrapper)


def sync_get_page_summary(page_id: str) -> str:
    """同步获取页面摘要"""
    from .sync_utils import run_async_safely
    
    def _async_wrapper():
        async def _inner():
            tools = NotionPageTools()
            try:
                return await tools.get_page_text_summary(page_id)
            finally:
                await tools.close()
        return _inner()
    
    return run_async_safely(_async_wrapper)


def sync_search_page_content(page_id: str, search_text: str) -> Dict[str, Any]:
    """同步搜索页面内容"""
    from .sync_utils import run_async_safely
    
    def _async_wrapper():
        async def _inner():
            tools = NotionPageTools()
            try:
                return await tools.search_page_content(page_id, search_text)
            finally:
                await tools.close()
        return _inner()
    
    return run_async_safely(_async_wrapper)

