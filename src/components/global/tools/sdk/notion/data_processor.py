"""
Notion数据处理模块

提供对Notion API返回数据的处理和转换功能，
将复杂的Notion数据结构转换为易于使用的格式。
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class NotionDataProcessor:
    """Notion数据处理器"""
    
    @staticmethod
    def extract_plain_text(rich_text: List[Dict[str, Any]]) -> str:
        """
        从Notion富文本对象中提取纯文本
        
        Args:
            rich_text: Notion富文本对象列表
            
        Returns:
            提取的纯文本
        """
        if not rich_text:
            return ""
        
        text_parts = []
        for text_obj in rich_text:
            if text_obj.get("type") == "text":
                content = text_obj.get("text", {}).get("content", "")
                text_parts.append(content)
        
        return "".join(text_parts)
    
    @staticmethod
    def process_property_value(prop_name: str, prop_data: Dict[str, Any]) -> Any:
        """
        处理数据库属性值
        
        Args:
            prop_name: 属性名称
            prop_data: 属性数据
            
        Returns:
            处理后的属性值
        """
        prop_type = prop_data.get("type")
        
        if prop_type == "title":
            return NotionDataProcessor.extract_plain_text(prop_data.get("title", []))
        
        elif prop_type == "rich_text":
            return NotionDataProcessor.extract_plain_text(prop_data.get("rich_text", []))
        
        elif prop_type == "number":
            return prop_data.get("number")
        
        elif prop_type == "select":
            select_data = prop_data.get("select")
            return select_data.get("name") if select_data else None
        
        elif prop_type == "multi_select":
            multi_select = prop_data.get("multi_select", [])
            return [item.get("name") for item in multi_select]
        
        elif prop_type == "date":
            date_data = prop_data.get("date")
            if date_data:
                return {
                    "start": date_data.get("start"),
                    "end": date_data.get("end"),
                    "time_zone": date_data.get("time_zone")
                }
            return None
        
        elif prop_type == "checkbox":
            return prop_data.get("checkbox", False)
        
        elif prop_type == "url":
            return prop_data.get("url")
        
        elif prop_type == "email":
            return prop_data.get("email")
        
        elif prop_type == "phone_number":
            return prop_data.get("phone_number")
        
        elif prop_type == "relation":
            relations = prop_data.get("relation", [])
            return [rel.get("id") for rel in relations]
        
        elif prop_type == "people":
            people = prop_data.get("people", [])
            return [{"id": person.get("id"), "name": person.get("name")} for person in people]
        
        elif prop_type == "files":
            files = prop_data.get("files", [])
            return [{"name": file.get("name"), "url": file.get("file", {}).get("url")} for file in files]
        
        elif prop_type == "created_time":
            return prop_data.get("created_time")
        
        elif prop_type == "last_edited_time":
            return prop_data.get("last_edited_time")
        
        elif prop_type == "formula":
            formula_data = prop_data.get("formula")
            if formula_data:
                formula_type = formula_data.get("type")
                return formula_data.get(formula_type)
            return None
        
        else:
            logger.warning(f"未知属性类型: {prop_type}")
            return str(prop_data)
    
    @staticmethod
    def process_database_page(page_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理数据库页面数据
        
        Args:
            page_data: 原始页面数据
            
        Returns:
            处理后的页面数据
        """
        processed = {
            "id": page_data.get("id"),
            "created_time": page_data.get("created_time"),
            "last_edited_time": page_data.get("last_edited_time"),
            "url": page_data.get("url"),
            "properties": {}
        }
        
        # 处理属性
        properties = page_data.get("properties", {})
        for prop_name, prop_data in properties.items():
            try:
                processed["properties"][prop_name] = NotionDataProcessor.process_property_value(
                    prop_name, prop_data
                )
            except Exception as e:
                logger.error(f"处理属性 {prop_name} 时出错: {e}")
                processed["properties"][prop_name] = None
        
        return processed
    
    @staticmethod
    def process_database_query_result(query_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理数据库查询结果
        
        Args:
            query_result: 原始查询结果
            
        Returns:
            处理后的查询结果
        """
        results = query_result.get("results", [])
        processed_results = []
        
        for page_data in results:
            try:
                processed_page = NotionDataProcessor.process_database_page(page_data)
                processed_results.append(processed_page)
            except Exception as e:
                logger.error(f"处理页面数据时出错: {e}")
                continue
        
        return {
            "results": processed_results,
            "has_more": query_result.get("has_more", False),
            "next_cursor": query_result.get("next_cursor"),
            "total_count": len(processed_results)
        }
    
    @staticmethod
    def extract_block_text(block: Dict[str, Any]) -> str:
        """
        从块中提取文本内容
        
        Args:
            block: 块数据
            
        Returns:
            提取的文本
        """
        block_type = block.get("type")
        text_content = ""
        
        if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item"]:
            block_data = block.get(block_type, {})
            rich_text = block_data.get("rich_text", [])
            text_content = NotionDataProcessor.extract_plain_text(rich_text)
        
        elif block_type == "to_do":
            todo_data = block.get("to_do", {})
            rich_text = todo_data.get("rich_text", [])
            checked = todo_data.get("checked", False)
            text_content = f"{'☑' if checked else '☐'} {NotionDataProcessor.extract_plain_text(rich_text)}"
        
        elif block_type == "code":
            code_data = block.get("code", {})
            rich_text = code_data.get("rich_text", [])
            language = code_data.get("language", "")
            code_text = NotionDataProcessor.extract_plain_text(rich_text)
            text_content = f"```{language}\n{code_text}\n```"
        
        elif block_type == "quote":
            quote_data = block.get("quote", {})
            rich_text = quote_data.get("rich_text", [])
            text_content = f"> {NotionDataProcessor.extract_plain_text(rich_text)}"
        
        return text_content
    
    @staticmethod
    def process_page_content(content_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理页面内容
        
        Args:
            content_result: 原始内容结果
            
        Returns:
            处理后的内容
        """
        blocks = content_result.get("results", [])
        processed_blocks = []
        full_text_content = []
        
        for block in blocks:
            try:
                processed_block = {
                    "id": block.get("id"),
                    "type": block.get("type"),
                    "created_time": block.get("created_time"),
                    "last_edited_time": block.get("last_edited_time"),
                    "has_children": block.get("has_children", False)
                }
                
                # 提取文本内容
                text_content = NotionDataProcessor.extract_block_text(block)
                processed_block["text_content"] = text_content
                
                if text_content.strip():
                    full_text_content.append(text_content)
                
                processed_blocks.append(processed_block)
                
            except Exception as e:
                logger.error(f"处理块数据时出错: {e}")
                continue
        
        return {
            "blocks": processed_blocks,
            "full_text": "\n".join(full_text_content),
            "has_more": content_result.get("has_more", False),
            "next_cursor": content_result.get("next_cursor"),
            "total_blocks": len(processed_blocks)
        }
    
    @staticmethod
    def process_search_result(search_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理搜索结果
        
        Args:
            search_result: 原始搜索结果
            
        Returns:
            处理后的搜索结果
        """
        results = search_result.get("results", [])
        processed_results = []
        
        for item in results:
            try:
                object_type = item.get("object")
                processed_item = {
                    "id": item.get("id"),
                    "object": object_type,
                    "created_time": item.get("created_time"),
                    "last_edited_time": item.get("last_edited_time"),
                    "url": item.get("url")
                }
                
                if object_type == "page":
                    # 处理页面
                    properties = item.get("properties", {})
                    title_prop = None
                    
                    # 查找标题属性
                    for prop_name, prop_data in properties.items():
                        if prop_data.get("type") == "title":
                            title_prop = prop_name
                            break
                    
                    if title_prop:
                        processed_item["title"] = NotionDataProcessor.process_property_value(
                            title_prop, properties[title_prop]
                        )
                    
                elif object_type == "database":
                    # 处理数据库
                    processed_item["title"] = NotionDataProcessor.extract_plain_text(
                        item.get("title", [])
                    )
                
                processed_results.append(processed_item)
                
            except Exception as e:
                logger.error(f"处理搜索结果项时出错: {e}")
                continue
        
        return {
            "results": processed_results,
            "has_more": search_result.get("has_more", False),
            "next_cursor": search_result.get("next_cursor"),
            "total_count": len(processed_results)
        }
    
    @staticmethod
    def format_for_display(data: Any, max_length: int = 1000) -> str:
        """
        格式化数据用于显示
        
        Args:
            data: 要格式化的数据
            max_length: 最大长度
            
        Returns:
            格式化后的字符串
        """
        if isinstance(data, dict):
            formatted = json.dumps(data, ensure_ascii=False, indent=2)
        elif isinstance(data, list):
            formatted = json.dumps(data, ensure_ascii=False, indent=2)
        else:
            formatted = str(data)
        
        if len(formatted) > max_length:
            formatted = formatted[:max_length] + "..."
        
        return formatted

