"""
Registry module for the Multi-AI-Agent project.
This module contains provider/model catalog and validation.
"""

from src.agents.langchain.agent_factory import get_available_configurations
from src.llm.langchain.utils import list_ollama_models


async def get_catalog():
    """Get the full provider/model catalog"""
    try:
        configs = get_available_configurations()
        
        if not configs["available_providers"]:
            return {
                "error": "No available LLM providers",
                "message": "Please ensure at least one API key is configured (ZHIPU_API_KEY or OPENAI_API_KEY)"
            }
        
        catalog = {
            "providers": [],
            "recommended": configs.get("recommended_configs", []),
            "default": configs.get("default_config", {})
        }
        
        for provider in configs["available_providers"]:
            provider_info = {
                "name": provider['name'],
                "provider": provider['provider'],
                "default_model": provider['default_model']
            }
            
            # Ollama special handling: show local available models and dynamic default model
            if provider['provider'] == 'ollama':
                try:
                    local_models = await list_ollama_models()
                    if local_models:
                        # Update default model to the first available local model
                        provider_info["default_model"] = local_models[0]
                        provider_info["local_models"] = local_models
                    else:
                        provider_info["default_model"] = None
                        provider_info["local_models"] = []
                        provider_info["message"] = "No local models available. Please run 'ollama pull <model>' to install models."
                except Exception as e:
                    provider_info["error"] = str(e)
            else:
                # Other providers show static supported model list
                if "models_detail" in provider:
                    provider_info["models"] = provider["models_detail"]
            
            catalog["providers"].append(provider_info)
        
        return catalog
        
    except Exception as e:
        return {
            "error": "Failed to get LLM catalog",
            "message": str(e)
        }


def validate(provider, model, catalog):
    """Validate requested provider/model switch"""
    # Check if provider exists
    provider_info = next((p for p in catalog["providers"] if p["provider"] == provider), None)
    if not provider_info:
        available_providers = [p["provider"] for p in catalog["providers"]]
        return {
            "valid": False,
            "error": f"Unsupported LLM provider: {provider}",
            "message": f"Available providers: {', '.join(available_providers)}"
        }
    
    # For Ollama, check if model is available locally
    if provider == 'ollama':
        if model and model not in provider_info.get("local_models", []):
            return {
                "valid": False,
                "error": f"Model not available locally: {model}",
                "message": f"Please run 'ollama pull {model}' to install the model"
            }
    
    return {"valid": True}


def resolve_default(provider, catalog):
    """Resolve default model if omitted"""
    provider_info = next((p for p in catalog["providers"] if p["provider"] == provider), None)
    if provider_info:
        return provider_info["default_model"]
    return None