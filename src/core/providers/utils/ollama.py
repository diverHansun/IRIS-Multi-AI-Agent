"""
Ollama Dynamic Model Discovery Utilities

Provides unified local Ollama model discovery functionality.
Supports both HTTP API and CLI methods.
This is a shared module used by both LLM and Agent modules.
"""

import json
import logging
import shutil
import subprocess
import asyncio
from typing import AsyncGenerator, List, Dict, Any

import aiohttp

from src.config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Direct HTTP client for Ollama API, used as fallback when LangChain streaming fails."""

    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def stream_chat(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.1,
    ) -> AsyncGenerator[str, None]:
        """Stream chat responses directly from Ollama HTTP API."""
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "top_k": 40,
            },
        }

        timeout_cfg = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"HTTP {response.status}: {error_text}")

                async for chunk in response.content:
                    if not chunk:
                        continue
                    try:
                        data = json.loads(chunk.decode("utf-8").strip())
                    except json.JSONDecodeError:
                        continue

                    message = data.get("message", {})
                    content = message.get("content")
                    if content:
                        yield content

                    if data.get("done"):
                        break

    async def simple_chat(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.1,
    ) -> str:
        """Send a non-streaming chat request."""
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "top_k": 40,
            },
        }

        timeout_cfg = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"HTTP {response.status}: {error_text}")

                data = await response.json()
                message = data.get("message", {})
                return message.get("content", "")

    async def health_check(self) -> bool:
        """Return True when Ollama service responds successfully."""
        timeout_cfg = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
                async with session.get(f"{self.base_url}/api/tags") as response:
                    return response.status == 200
        except Exception:
            return False


async def get_ollama_models_http(base_url: str, timeout: int = 8) -> List[str]:
    """
    Get Ollama model list via HTTP API

    Args:
        base_url: Ollama service URL
        timeout: Request timeout in seconds

    Returns:
        List[str]: Model name list, empty list on failure
    """
    url = base_url.rstrip('/') + '/api/tags'

    try:
        timeout_config = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            logger.debug(f"Attempting HTTP Ollama model fetch: {url}")

            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    models = [
                        model.get('name')
                        for model in data.get('models', [])
                        if model.get('name')
                    ]
                    logger.info(f"Retrieved {len(models)} Ollama models via HTTP")
                    logger.debug(f"HTTP model list: {models}")
                    return models
                else:
                    logger.warning(f"HTTP request failed with status: {response.status}")
                    return []

    except asyncio.TimeoutError:
        logger.warning(f"HTTP request timeout ({timeout}s): {url}")
        return []
    except aiohttp.ClientConnectorError:
        logger.debug("Cannot connect to Ollama service, may not be running")
        return []
    except Exception as e:
        logger.debug(f"HTTP request exception: {str(e)}")
        return []


def get_ollama_models_cli() -> List[str]:
    """
    Get Ollama model list via CLI command

    Returns:
        List[str]: Model name list, empty list on failure
    """
    if not shutil.which('ollama'):
        logger.debug("ollama CLI command not found")
        return []

    try:
        logger.debug("Attempting CLI Ollama model fetch")

        result = subprocess.run(
            ['ollama', 'list', '--format', 'json'],
            capture_output=True,
            text=True,
            timeout=10,
            encoding='utf-8'
        )

        if result.returncode == 0:
            try:
                data = json.loads(result.stdout or '{}')
                models = [
                    model.get('name')
                    for model in data.get('models', [])
                    if model.get('name')
                ]
                logger.info(f"Retrieved {len(models)} Ollama models via CLI")
                logger.debug(f"CLI model list: {models}")
                return models
            except json.JSONDecodeError as e:
                logger.warning(f"CLI JSON output parse failed: {e}")
                return _parse_ollama_list_text(result.stdout)
        else:
            logger.warning(f"CLI command failed with return code: {result.returncode}")
            logger.debug(f"CLI error output: {result.stderr}")
            return []

    except subprocess.TimeoutExpired:
        logger.warning("CLI command execution timeout")
        return []
    except Exception as e:
        logger.debug(f"CLI command execution exception: {str(e)}")
        return []


def _parse_ollama_list_text(output: str) -> List[str]:
    """
    Parse ollama list text format output (compatibility handling)

    Args:
        output: Text output from ollama list

    Returns:
        List[str]: Model name list
    """
    models = []
    lines = output.strip().split('\n')

    for line in lines:
        if not line.strip() or line.startswith('NAME'):
            continue

        parts = line.split()
        if parts:
            model_name = parts[0]
            if model_name and ':' in model_name:
                models.append(model_name)

    logger.debug(f"Text parsing yielded models: {models}")
    return models


async def list_ollama_models(base_url: str = None, timeout: int = 8) -> List[str]:
    """
    Get locally available Ollama model list

    Prioritizes HTTP API, falls back to CLI command on failure

    Args:
        base_url: Ollama service URL, uses config default if None
        timeout: HTTP request timeout in seconds

    Returns:
        List[str]: Model name list in discovery order
    """
    if base_url is None:
        base_url = settings.ollama_base_url

    logger.debug(f"Starting Ollama model discovery, base_url: {base_url}")

    models = await get_ollama_models_http(base_url, timeout)
    if models:
        logger.info(f"Successfully discovered {len(models)} models via HTTP")
        return models

    logger.debug("HTTP method failed, trying CLI method")
    models = get_ollama_models_cli()
    if models:
        logger.info(f"Successfully discovered {len(models)} models via CLI")
        return models

    logger.info("No Ollama models discovered")
    return []


def get_model_display_info(models: List[str]) -> List[Dict[str, Any]]:
    """
    Add display information to model list (for CLI-friendly output)

    Args:
        models: Model name list

    Returns:
        List[Dict]: Model list with display information
    """
    model_info = []

    for model in models:
        info = {
            'name': model,
            'display_name': model,
            'description': _infer_model_description(model)
        }
        model_info.append(info)

    return model_info


def _infer_model_description(model_name: str) -> str:
    """
    Infer description based on model name

    Args:
        model_name: Model name

    Returns:
        str: Model description
    """
    name_lower = model_name.lower()

    if any(keyword in name_lower for keyword in ['qwen', 'chatglm', 'baichuan']):
        return "Chinese-optimized model"

    if any(keyword in name_lower for keyword in ['code', 'deepseek', 'starcoder']):
        return "Code-specialized model"

    if any(keyword in name_lower for keyword in ['reasoning', 'think', 'r1']):
        return "Reasoning-specialized model"

    if any(keyword in name_lower for keyword in ['mini', 'small', '1b', '3b']):
        return "Lightweight efficient model"

    if any(keyword in name_lower for keyword in ['20b', '70b', 'large']):
        return "Large general-purpose model"

    if 'gemma' in name_lower:
        return "Google Gemma model"
    elif 'llama' in name_lower:
        return "Meta Llama model"
    elif 'mistral' in name_lower:
        return "Mistral AI model"

    return "General conversational model"


async def discover_models() -> List[str]:
    """Convenience function to discover local Ollama models"""
    return await list_ollama_models()


def is_ollama_available() -> bool:
    """
    Check if Ollama is available (synchronous version for quick detection)

    Returns:
        bool: Whether Ollama is available
    """
    return bool(shutil.which('ollama'))
