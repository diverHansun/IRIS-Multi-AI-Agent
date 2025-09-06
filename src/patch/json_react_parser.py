"""
自定义的 ReAct 输出解析器，支持 JSON 格式的工具输入
"""

import json
import re
from typing import Union

from langchain.agents.output_parsers import ReActSingleInputOutputParser
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.exceptions import OutputParserException

# 定义常量
FINAL_ANSWER_ACTION = "Final Answer:"
FINAL_ANSWER_AND_PARSABLE_ACTION_ERROR_MESSAGE = (
    "Parsing LLM output produced both a final answer and a parse-able action:"
)
MISSING_ACTION_AFTER_THOUGHT_ERROR_MESSAGE = "Missing 'Action:' after 'Thought:"
MISSING_ACTION_INPUT_AFTER_ACTION_ERROR_MESSAGE = (
    "Missing 'Action Input:' after 'Action:'"
)


class JSONReActSingleInputOutputParser(ReActSingleInputOutputParser):
    """ReAct Output parser that can parse JSON action inputs."""
    
    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        includes_answer = FINAL_ANSWER_ACTION in text
        regex = (
            r"Action\s*\d*\s*:[\s]*(.*?)[\s]*Action\s*\d*\s*Input\s*\d*\s*:[\s]*(.*)"
        )
        action_match = re.search(regex, text, re.DOTALL)
        if action_match:
            if includes_answer:
                msg = f"{FINAL_ANSWER_AND_PARSABLE_ACTION_ERROR_MESSAGE}: {text}"
                raise OutputParserException(msg)
            action = action_match.group(1).strip()
            action_input = action_match.group(2)
            tool_input = action_input.strip(" ")
            tool_input = tool_input.strip('"')
            
            # 尝试解析 JSON 格式的输入
            try:
                # 如果输入是 JSON 格式，则解析为字典
                if tool_input.startswith('{') and tool_input.endswith('}'):
                    tool_input = json.loads(tool_input)
                elif tool_input.startswith('[') and tool_input.endswith(']'):
                    tool_input = json.loads(tool_input)
            except json.JSONDecodeError:
                # 如果不是有效的 JSON，保持原样作为字符串
                pass

            return AgentAction(action, tool_input, text)

        if includes_answer:
            return AgentFinish(
                {"output": text.split(FINAL_ANSWER_ACTION)[-1].strip()},
                text,
            )

        if not re.search(r"Action\s*\d*\s*:[\s]*(.*?)", text, re.DOTALL):
            msg = f"Could not parse LLM output: `{text}`"
            raise OutputParserException(
                msg,
                observation=MISSING_ACTION_AFTER_THOUGHT_ERROR_MESSAGE,
                llm_output=text,
                send_to_llm=True,
            )
        if not re.search(
            r"[\s]*Action\s*\d*\s*Input\s*\d*\s*:[\s]*(.*)",
            text,
            re.DOTALL,
        ):
            msg = f"Could not parse LLM output: `{text}`"
            raise OutputParserException(
                msg,
                observation=MISSING_ACTION_INPUT_AFTER_ACTION_ERROR_MESSAGE,
                llm_output=text,
                send_to_llm=True,
            )
        msg = f"Could not parse LLM output: `{text}`"
        raise OutputParserException(msg)