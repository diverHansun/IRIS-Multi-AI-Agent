"""
Notion搜索工具

提供对Notion工作区的全局搜索功能。
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Any
from difflib import SequenceMatcher

from .client import NotionClient, create_notion_client
from .data_processor import NotionDataProcessor

logger = logging.getLogger(__name__)


class NotionSearchTools:
    """Notion搜索工具类"""
    
    def __init__(self, client: Optional[NotionClient] = None):
        """
        初始化搜索工具
        
        Args:
            client: Notion客户端，如果不提供则创建默认客户端
        """
        self.client = client or create_notion_client()
        self.processor = NotionDataProcessor()
    
    async def search_all(
        self, 
        query: str, 
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        在整个Notion工作区中搜索（智能匹配增强版）
        
        Args:
            query: 搜索查询
            limit: 限制返回结果数
            
        Returns:
            搜索结果
        """
        try:
            logger.info(f"智能搜索: {query}")
            
            # 扩大搜索范围以获得更多候选结果
            page_size = min((limit or 10) * 3, 100)  # 获取3倍的结果用于智能过滤
            raw_result = await self.client.search(
                query=query,
                page_size=page_size
            )
            
            processed_result = self.processor.process_search_result(raw_result)
            
            # 应用智能匹配算法
            enhanced_result = self._apply_smart_matching(query, processed_result, limit)
            
            return enhanced_result
            
        except Exception as e:
            logger.error(f"智能搜索失败: {e}")
            raise
    
    async def search_databases(
        self, 
        query: str, 
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        搜索数据库
        
        Args:
            query: 搜索查询
            limit: 限制返回结果数
            
        Returns:
            数据库搜索结果
        """
        try:
            logger.info(f"搜索数据库: {query}")
            
            # 构建数据库过滤条件
            filter_condition = {
                "value": "database",
                "property": "object"
            }
            
            page_size = min(limit or 100, 100)
            raw_result = await self.client.search(
                query=query,
                filter_conditions=filter_condition,
                page_size=page_size
            )
            
            return self.processor.process_search_result(raw_result)
            
        except Exception as e:
            logger.error(f"搜索数据库失败: {e}")
            raise
    
    async def search_pages(
        self, 
        query: str, 
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        搜索页面
        
        Args:
            query: 搜索查询
            limit: 限制返回结果数
            
        Returns:
            页面搜索结果
        """
        try:
            logger.info(f"搜索页面: {query}")
            
            # 构建页面过滤条件
            filter_condition = {
                "value": "page",
                "property": "object"
            }
            
            page_size = min(limit or 100, 100)
            raw_result = await self.client.search(
                query=query,
                filter_conditions=filter_condition,
                page_size=page_size
            )
            
            return self.processor.process_search_result(raw_result)
            
        except Exception as e:
            logger.error(f"搜索页面失败: {e}")
            raise
    
    async def search_with_type_filter(
        self,
        query: str,
        object_type: str,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        根据对象类型搜索
        
        Args:
            query: 搜索查询
            object_type: 对象类型（page 或 database）
            limit: 限制返回结果数
            
        Returns:
            搜索结果
        """
        if object_type == "database":
            return await self.search_databases(query, limit)
        elif object_type == "page":
            return await self.search_pages(query, limit)
        else:
            return await self.search_all(query, limit)
    
    async def get_search_summary(self, query: str) -> str:
        """
        获取搜索结果摘要
        
        Args:
            query: 搜索查询
            
        Returns:
            搜索摘要文本
        """
        try:
            # 执行搜索
            search_result = await self.search_all(query, limit=20)
            
            # 构建摘要
            results = search_result['results']
            summary_parts = [
                f"搜索词: '{query}'",
                f"找到 {len(results)} 个结果"
            ]
            
            if results:
                # 按类型分组
                databases = [r for r in results if r['object'] == 'database']
                pages = [r for r in results if r['object'] == 'page']
                
                if databases:
                    summary_parts.append(f"\\n数据库 ({len(databases)}个):")
                    for i, db in enumerate(databases[:3]):
                        title = db.get('title', '无标题')
                        summary_parts.append(f"{i+1}. {title}")
                    if len(databases) > 3:
                        summary_parts.append(f"   ...还有{len(databases) - 3}个数据库")
                
                if pages:
                    summary_parts.append(f"\\n页面 ({len(pages)}个):")
                    for i, page in enumerate(pages[:3]):
                        title = page.get('title', '无标题')
                        summary_parts.append(f"{i+1}. {title}")
                    if len(pages) > 3:
                        summary_parts.append(f"   ...还有{len(pages) - 3}个页面")
            else:
                summary_parts.append("\\n未找到相关内容")
            
            return "\\n".join(summary_parts)
            
        except Exception as e:
            logger.error(f"获取搜索摘要失败: {e}")
            return f"搜索时出错: {str(e)}"
    
    def _apply_smart_matching(self, query: str, search_result: Dict[str, Any], limit: Optional[int] = None) -> Dict[str, Any]:
        """
        应用智能匹配算法优化搜索结果
        
        Args:
            query: 原始搜索查询
            search_result: 原始搜索结果
            limit: 结果数量限制
            
        Returns:
            优化后的搜索结果
        """
        results = search_result.get('results', [])
        if not results:
            return search_result
        
        # 计算每个结果的匹配分数
        scored_results = []
        for result in results:
            title = result.get('title', '')
            score = self._calculate_match_score(query, title)
            scored_results.append((score, result))
        
        # 按分数排序（分数越高越好）
        scored_results.sort(key=lambda x: x[0], reverse=True)
        
        # 提取排序后的结果
        sorted_results = [result for score, result in scored_results]
        
        # 应用限制
        if limit:
            sorted_results = sorted_results[:limit]
        
        # 返回优化后的结果
        return {
            'results': sorted_results,
            'has_more': search_result.get('has_more', False),
            'next_cursor': search_result.get('next_cursor'),
            'total_count': len(sorted_results)
        }
    
    def _calculate_match_score(self, query: str, title: str) -> float:
        """
        计算查询与标题的匹配分数
        
        Args:
            query: 搜索查询
            title: 页面/数据库标题
            
        Returns:
            匹配分数（0-100）
        """
        if not title:
            return 0.0
        
        query_lower = query.lower().strip()
        title_lower = title.lower().strip()
        
        # 1. 精确匹配（最高分）
        if query_lower == title_lower:
            return 100.0
        
        # 2. 包含匹配
        if query_lower in title_lower:
            # 根据匹配位置和比例给分
            match_ratio = len(query_lower) / len(title_lower)
            position_bonus = 1.0 if title_lower.startswith(query_lower) else 0.5
            return 80.0 + (match_ratio * 15.0) + (position_bonus * 5.0)
        
        # 3. 字符串相似度匹配
        similarity = SequenceMatcher(None, query_lower, title_lower).ratio()
        base_score = similarity * 70.0
        
        # 4. 特殊的日期格式匹配
        date_bonus = self._calculate_date_match_bonus(query, title)
        
        # 5. 关键词匹配加分
        keyword_bonus = self._calculate_keyword_bonus(query, title)
        
        return min(base_score + date_bonus + keyword_bonus, 99.0)
    
    def _calculate_date_match_bonus(self, query: str, title: str) -> float:
        """
        计算日期格式的特殊匹配加分
        
        Args:
            query: 搜索查询
            title: 标题
            
        Returns:
            日期匹配加分（0-20）
        """
        # 日期格式模式
        date_patterns = [
            r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',  # YYYY/MM/DD 或 YYYY-MM-DD
            r'(\d{1,2})[/-](\d{1,2})',              # MM/DD 或 MM-DD
            r'(\d{4})年(\d{1,2})月(\d{1,2})日?',      # YYYY年MM月DD日
        ]
        
        query_dates = []
        title_dates = []
        
        # 从查询和标题中提取日期成分
        for pattern in date_patterns:
            query_matches = re.findall(pattern, query)
            title_matches = re.findall(pattern, title)
            query_dates.extend(query_matches)
            title_dates.extend(title_matches)
        
        if not query_dates or not title_dates:
            return 0.0
        
        # 比较日期成分的匹配度
        max_bonus = 0.0
        for q_date in query_dates:
            for t_date in title_dates:
                bonus = self._compare_date_components(q_date, t_date)
                max_bonus = max(max_bonus, bonus)
        
        return max_bonus
    
    def _compare_date_components(self, date1, date2) -> float:
        """
        比较两个日期元组的匹配程度
        
        Args:
            date1: 第一个日期元组
            date2: 第二个日期元组
            
        Returns:
            匹配分数（0-20）
        """
        # 确保都是元组格式
        if isinstance(date1, str):
            date1 = (date1,)
        if isinstance(date2, str):
            date2 = (date2,)
        
        # 标准化为相同长度（年、月、日）
        def normalize_date(date_tuple):
            if len(date_tuple) == 1:
                return ('', '', date_tuple[0])  # 只有日期
            elif len(date_tuple) == 2:
                return ('', date_tuple[0], date_tuple[1])  # 月和日
            elif len(date_tuple) == 3:
                return date_tuple  # 年、月、日
            return ('', '', '')
        
        norm_date1 = normalize_date(date1)
        norm_date2 = normalize_date(date2)
        
        matches = 0
        total_components = 0
        
        for i, (c1, c2) in enumerate(zip(norm_date1, norm_date2)):
            if c1 and c2:  # 两个都不为空
                total_components += 1
                if c1.zfill(2) == c2.zfill(2):  # 补零比较
                    matches += 1
        
        if total_components == 0:
            return 0.0
        
        match_ratio = matches / total_components
        return match_ratio * 20.0  # 最高20分
    
    def _calculate_keyword_bonus(self, query: str, title: str) -> float:
        """
        计算关键词匹配加分
        
        Args:
            query: 搜索查询
            title: 标题
            
        Returns:
            关键词匹配加分（0-10）
        """
        query_words = set(re.findall(r'\w+', query.lower()))
        title_words = set(re.findall(r'\w+', title.lower()))
        
        if not query_words:
            return 0.0
        
        # 计算交集比例
        intersection = query_words.intersection(title_words)
        match_ratio = len(intersection) / len(query_words)
        
        return match_ratio * 10.0  # 最高10分
    
    async def search_smart(self, query: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        智能搜索：结合多种策略找到最相关的结果
        
        Args:
            query: 搜索查询
            limit: 限制返回结果数
            
        Returns:
            搜索结果
        """
        try:
            logger.info(f"执行智能搜索: {query}")
            
            # 策略1: 标准搜索
            standard_results = await self.search_all(query, limit)
            
            # 如果找到精确匹配，直接返回
            for result in standard_results.get('results', []):
                if result.get('title', '').lower().strip() == query.lower().strip():
                    logger.info("找到精确匹配，返回标准搜索结果")
                    return standard_results
            
            # 策略2: 分词搜索（针对日期等复合查询）
            alternative_queries = self._generate_alternative_queries(query)
            all_results = list(standard_results.get('results', []))
            
            for alt_query in alternative_queries:
                if alt_query != query:  # 避免重复搜索
                    try:
                        alt_results = await self.search_all(alt_query, limit)
                        all_results.extend(alt_results.get('results', []))
                    except Exception as e:
                        logger.warning(f"备选查询 '{alt_query}' 失败: {e}")
            
            # 去重并重新排序
            unique_results = self._deduplicate_results(all_results)
            final_result = self._apply_smart_matching(query, {'results': unique_results}, limit)
            
            logger.info(f"智能搜索完成，返回 {len(final_result.get('results', []))} 个结果")
            return final_result
            
        except Exception as e:
            logger.error(f"智能搜索失败: {e}")
            # 降级到标准搜索
            return await self.search_all(query, limit)
    
    def _generate_alternative_queries(self, query: str) -> List[str]:
        """
        生成备选搜索查询
        
        Args:
            query: 原始查询
            
        Returns:
            备选查询列表
        """
        alternatives = [query]
        
        # 针对日期格式生成备选查询
        date_match = re.match(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', query)
        if date_match:
            year, month, day = date_match.groups()
            alternatives.extend([
                f"{month}/{day}",
                f"{year}年{month}月{day}日",
                f"{year}-{month}-{day}",
                year,  # 只搜索年份
            ])
        
        # 针对含有空格的查询
        if ' ' in query:
            words = query.split()
            alternatives.extend(words)  # 搜索单个词
        
        # 针对含有特殊字符的查询
        if any(char in query for char in ['/', '-', '_', '.']):  
            # 移除特殊字符
            clean_query = re.sub(r'[/-_.]+', ' ', query)
            alternatives.append(clean_query.strip())
        
        return list(set(alternatives))  # 去重
    
    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        去重搜索结果
        
        Args:
            results: 结果列表
            
        Returns:
            去重后的结果列表
        """
        seen_ids = set()
        unique_results = []
        
        for result in results:
            result_id = result.get('id')
            if result_id and result_id not in seen_ids:
                seen_ids.add(result_id)
                unique_results.append(result)
        
        return unique_results
    
    async def close(self):
        """关闭客户端连接"""
        await self.client.close()


# 同步包装函数，用于LangChain工具集成
def sync_search_notion(query: str, limit: Optional[int] = None) -> Dict[str, Any]:
    """同步搜索Notion"""
    try:
        # 简单的同步包装，避免复杂的事件循环处理
        import asyncio
        
        async def _async_wrapper():
            tools = NotionSearchTools()
            try:
                return await tools.search_all(query, limit)
            finally:
                await tools.close()
        
        # 尝试直接运行
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，使用asyncio.run
                return asyncio.run(_async_wrapper())
            else:
                return loop.run_until_complete(_async_wrapper())
        except RuntimeError:
            # 没有事件循环，创建新的
            return asyncio.run(_async_wrapper())
            
    except Exception as e:
        logger.error(f"同步搜索Notion失败: {e}")
        return {
            "results": [],
            "has_more": False,
            "next_cursor": None,
            "total_count": 0,
            "error": str(e)
        }


def sync_search_databases(query: str, limit: Optional[int] = None) -> Dict[str, Any]:
    """同步搜索数据库"""
    try:
        import asyncio
        
        async def _async_wrapper():
            tools = NotionSearchTools()
            try:
                return await tools.search_databases(query, limit)
            finally:
                await tools.close()
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return asyncio.run(_async_wrapper())
            else:
                return loop.run_until_complete(_async_wrapper())
        except RuntimeError:
            return asyncio.run(_async_wrapper())
            
    except Exception as e:
        logger.error(f"同步搜索数据库失败: {e}")
        return {
            "results": [],
            "has_more": False,
            "next_cursor": None,
            "total_count": 0,
            "error": str(e)
        }


def sync_search_pages(query: str, limit: Optional[int] = None) -> Dict[str, Any]:
    """同步搜索页面"""
    from .sync_utils import run_async_safely
    
    def _async_wrapper():
        async def _inner():
            tools = NotionSearchTools()
            try:
                return await tools.search_pages(query, limit)
            finally:
                await tools.close()
        return _inner()
    
    return run_async_safely(_async_wrapper)


def sync_get_search_summary(query: str) -> str:
    """同步获取搜索摘要"""
    from .sync_utils import run_async_safely
    
    def _async_wrapper():
        async def _inner():
            tools = NotionSearchTools()
            try:
                return await tools.get_search_summary(query)
            finally:
                await tools.close()
        return _inner()
    
    return run_async_safely(_async_wrapper)


def sync_search_notion_smart(query: str, limit: Optional[int] = None) -> Dict[str, Any]:
    """同步智能搜索Notion"""
    from .sync_utils import run_async_safely
    
    def _async_wrapper():
        async def _inner():
            tools = NotionSearchTools()
            try:
                return await tools.search_smart(query, limit)
            finally:
                await tools.close()
        return _inner()
    
    return run_async_safely(_async_wrapper)

