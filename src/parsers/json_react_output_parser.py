"""
JSON-first ReAct Output Parser

Enhances LangChain's ReActSingleInputOutputParser to support:
- Top-level strict JSON outputs with keys: thought, action, action_input, final_answer
- Light preprocessing: strip ```json fences, replace full-width quotes, tolerate trailing commas
- Fallback to classic ReAct format: "Action:" / "Action Input:" / "Final Answer:"
"""

from __future__ import annotations

import json
import re
from typing import Union, Optional

from langchain.agents.output_parsers import ReActSingleInputOutputParser
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.exceptions import OutputParserException


FINAL_ANSWER_ACTION = "Final Answer:"
FINAL_ANSWER_AND_PARSABLE_ACTION_ERROR_MESSAGE = (
    "Parsing LLM output produced both a final answer and a parse-able action:"
)
MISSING_ACTION_AFTER_THOUGHT_ERROR_MESSAGE = "Missing 'Action:' after 'Thought:'"
MISSING_ACTION_INPUT_AFTER_ACTION_ERROR_MESSAGE = (
    "Missing 'Action Input:' after 'Action:'"
)

ALLOWED_JSON_KEYS = {"thought", "action", "action_input", "final_answer"}


def _strip_code_fences(text: str) -> str:
    t = text.strip()
    # Remove leading and trailing ``` or ```json fences if present
    if t.startswith("```"):
        # drop first fence line
        t = re.sub(r"^```(?:json)?\s*\n?", "", t, flags=re.IGNORECASE)
    if t.endswith("```"):
        t = re.sub(r"\n?```\s*$", "", t)
    return t.strip()


def _replace_full_width_quotes(text: str) -> str:
    return text.replace("“", '"').replace("”", '"').replace("＂", '"')


def _remove_trailing_commas(text: str) -> str:
    # Remove trailing commas before } or ]
    return re.sub(r",\s*([}\]])", r"\1", text)


def _extract_first_json_object(text: str) -> Optional[str]:
    # Find first top-level JSON object substring { ... }
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


class JSONReActSingleInputOutputParser(ReActSingleInputOutputParser):
    """ReAct Output parser supporting strict JSON and classic ReAct formats."""

    def _try_parse_top_level_json(self, text: str) -> Optional[Union[AgentAction, AgentFinish]]:
        raw = _strip_code_fences(text)
        raw = _replace_full_width_quotes(raw)
        candidate = _extract_first_json_object(raw) or raw
        candidate = _remove_trailing_commas(candidate)

        try:
            obj = json.loads(candidate)
        except Exception:
            return None

        if not isinstance(obj, dict):
            return None

        # Ensure only allowed keys are present
        keys = set(obj.keys())
        if not keys.issubset(ALLOWED_JSON_KEYS):
            # Not our JSON contract
            return None

        # final_answer branch
        if "final_answer" in obj:
            if any(k in obj for k in ("action", "action_input")):
                msg = f"{FINAL_ANSWER_AND_PARSABLE_ACTION_ERROR_MESSAGE}: {text}"
                raise OutputParserException(msg)
            answer = str(obj["final_answer"]).strip()
            return AgentFinish({"output": answer}, text)

        # action branch
        if "action" in obj:
            if "action_input" not in obj:
                raise OutputParserException(
                    "Missing 'action_input' for action JSON",
                    observation=(
                        "Please output a JSON object with keys: 'thought' (optional), "
                        "'action' (string), and 'action_input' (object)."
                    ),
                    llm_output=text,
                    send_to_llm=True,
                )
            action = str(obj["action"]).strip()
            action_input = obj["action_input"]
            return AgentAction(action, action_input, text)

        # No actionable fields
        return None

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        # First try strict JSON mode
        result = self._try_parse_top_level_json(text)
        if result is not None:
            return result

        # Fallback: classic ReAct parser with JSON action input support
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

            # Try to parse JSON tool input if it looks like JSON
            try:
                if (tool_input.startswith('{') and tool_input.endswith('}')) or (
                    tool_input.startswith('[') and tool_input.endswith(']')
                ):
                    tool_input = json.loads(tool_input)
            except json.JSONDecodeError:
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

