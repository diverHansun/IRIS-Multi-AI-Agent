# DeepAgents Implementation

## Overview

DeepAgents implementation follows the same architectural pattern as basicagents, providing a consistent development experience while adding advanced multi-agent capabilities through middleware integration.

## Architecture Components

### Directory Structure
```
src/agents/deepagents/
├── __init__.py
├── managers/          # DeepAgents information and lifecycle
│   ├── __init__.py
│   └── deep_agent_manager.py
├── factories/         # Function-based agent creation factories
│   ├── __init__.py
│   ├── base.py
│   ├── research_factory.py
│   ├── coding_factory.py
│   └── analysis_factory.py
├── adapters/          # Single-layer configuration adapters
│   ├── __init__.py
│   ├── base.py
│   ├── research_adapter.py
│   ├── coding_adapter.py
│   └── analysis_adapter.py
└── instances/       # Concrete DeepAgent implementations
    ├── __init__.py
    ├── base_deep_agent.py
    ├── research_agent.py
    ├── coding_agent.py
    └── analysis_agent.py
```

## Implementation Flow

### 1. Manager Layer

#### DeepAgentManager
```python
# src/agents/deepagents/managers/deep_agent_manager.py
class DeepAgentManager:
    def __init__(self):
        from src.core.providers import provider_registry
        self.provider_registry = provider_registry
        self.factory_registry = DeepAgentFactoryRegistry()
        self.subagent_manager = SubAgentManager(provider_registry)
    
    async def create_deep_agent(self, provider: str, model: str, **user_params):
        """Create deep agent instance"""
        # 1. Get provider configuration
        provider_config = self._get_provider_config(provider)
        
        # 2. Create LLM adapter
        llm_adapter = self._create_llm_adapter(provider, model)
        
        # 3. Create agent adapter with middleware support
        agent_adapter = self._create_agent_adapter(provider, model)
        
        # 4. Get factory and create agent
        factory = self.factory_registry.get_factory(provider)
        return await factory.create_deep_agent_with_adapters(
            model=model,
            llm_adapter=llm_adapter,
            agent_adapter=agent_adapter,
            subagent_manager=self.subagent_manager,
            **user_params
        )
```

### 2. Factory Layer

#### BaseDeepAgentFactory
```python
# src/agents/deepagents/factories/base.py
class BaseDeepAgentFactory(ABC):
    def __init__(self, function_type: str):
        self.function_type = function_type
    
    @abstractmethod
    async def create_agent(
        self,
        provider: str,
        model: str,
        **kwargs
    ) -> Any:
        """Create function-specific agent instance"""
        pass
```

#### Function-Specific Factories
```python
# src/agents/deepagents/factories/research_factory.py
class ResearchFactory(BaseDeepAgentFactory):
    def __init__(self):
        super().__init__(function_type="research")
        self.provider_registry = provider_registry
    
    async def create_agent(
        self,
        provider: str,
        model: str,
        **kwargs
    ) -> ResearchAgent:
        """Create research agent"""
        adapter = ResearchAdapter(provider, model)
        return ResearchAgent(
            adapter=adapter,
            config=adapter.get_research_agent_config()
        )
    
    def get_available_models(self) -> List[str]:
        """Get available research models"""
        config = self.provider_registry.get_models_config()
        return list(config.get("research", {}).keys())
```

### 3. Adapter Layer

#### BaseDeepAgentAdapter
```python
# src/agents/deepagents/adapters/base.py
class BaseDeepAgentAdapter(ABC):
    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        self.config = self._load_config(provider, model)
    
    def create_llm(self):
        """Create LLM using unified OpenAI interface"""
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            base_url=self.config["base_url"],
            api_key=os.getenv(self.config["api_key_env"]),
            model_name=self.model,
            temperature=self.config.get("temperature", 0.1),
            max_tokens=self.config.get("max_tokens", 4000)
        )
    
    @abstractmethod
    def get_agent_config(self) -> Dict[str, Any]:
        """Get function-specific agent configuration"""
        pass
```

#### Function-Specific Adapters
```python
# src/agents/deepagents/adapters/research_adapter.py
class ResearchAdapter(BaseDeepAgentAdapter):
    def __init__(self, provider: str, model: str):
        super().__init__(provider, model)
    
    def get_agent_config(self) -> Dict[str, Any]:
        """Get research agent configuration"""
        return {
            "system_prompt": self._get_research_prompt(),
            "tools": self._get_research_tools(),
            "middleware": self._get_research_middleware()
        }
    
    def _get_research_prompt(self) -> str:
        """Load research-specific prompt"""
        from src.components.deepagents.prompts.registry import DeepAgentPromptRegistry
        return DeepAgentPromptRegistry().get_subagent_prompt("research")
```

### 4. Instance Layer

#### BaseDeepAgent
```python
# src/agents/deepagents/instances/base_deep_agent.py
class BaseDeepAgent(ABC):
    def __init__(
        self,
        model: str,
        provider: str,
        llm_adapter: Any,
        agent_adapter: Any,
        subagent_manager: SubAgentManager,
        **kwargs
    ):
        self.model = model
        self.provider = provider
        self.llm_adapter = llm_adapter
        self.agent_adapter = agent_adapter
        self.subagent_manager = subagent_manager
        
        # Initialize middleware
        self.middleware = self._initialize_middleware()
        
        # Initialize agent graph
        self.agent_graph = None
    
    def _initialize_middleware(self) -> List[AgentMiddleware]:
        """Initialize middleware components"""
        middleware_config = self.agent_adapter.get_deep_agent_mode_defaults()
        
        middleware = []
        
        # Filesystem middleware
        if middleware_config.get("middleware", {}).get("filesystem", {}).get("enabled", False):
            filesystem_config = middleware_config["middleware"]["filesystem"]
            middleware.append(FilesystemMiddleware(filesystem_config))
        
        # Subagent middleware
        if middleware_config.get("middleware", {}).get("subagents", {}).get("enabled", False):
            subagents_config = middleware_config["middleware"]["subagents"]
            middleware.append(SubAgentMiddleware(
                subagent_manager=self.subagent_manager,
                config=subagents_config
            ))
        
        return middleware
    
    async def _build_agent_graph(self):
        """Build agent graph with middleware"""
        if not self.llm_adapter:
            raise ValueError("LLM adapter is required")
        
        # Create agent with middleware
        self.agent_graph = create_agent(
            model=self.llm_adapter.create_llm(),
            tools=self._get_tools(),
            middleware=self.middleware,
            checkpointer=self._get_checkpointer()
        )
```

## Service Integration

### DeepAgentService
```python
# src/application/services/agent/deep/service.py
class DeepAgentService(BaseEngineService):
    def __init__(self):
        from src.agents.deepagents.managers import deep_agent_manager
        self.deep_agent_manager = deep_agent_manager
    
    async def initialize(self, ctx) -> Dict[str, Any]:
        """Initialize deep agent service"""
        config = self._config(ctx)
        config["agent_type"] = "deep"
        
        # Create deep agent
        agent = await self.deep_agent_manager.create_deep_agent(
            provider=config.get("provider"),
            model=config.get("model"),
            global_memory_manager=ctx.global_memory
        )
        
        config["agent_instance"] = agent
        return {
            "type": "success",
            "message": "Deep agent initialized",
            "payload": {
                "agent": agent.get_info(),
                "mode": {
                    "mode": "agent",
                    "agent_type": "deep",
                    "middleware": ["filesystem", "subagents"]
                }
            }
        }
```

## Configuration Integration

### Provider Registry Extension
```python
# src/core/providers/provider_registry.py
class ProviderRegistry:
    def __init__(self):
        # Existing provider configuration
        self._providers = {}
        
        # Deep agents configuration
        self.deep_config_loader = DeepConfigLoader()
        self._deep_config = None
    
    def get_deep_agent_config(self) -> Dict[str, Any]:
        """Get deep agent configuration"""
        if self._deep_config is None:
            self._deep_config = self.deep_config_loader.load_middleware_config()
        return self._deep_config
    
    def get_models_config(self) -> Dict[str, Any]:
        """Get models configuration"""
        return self.deep_config_loader.load_models_config()
```

## Subagent Management

### SubAgentManager
```python
# src/agents/deepagents/managers/subagent_manager.py
class SubAgentManager:
    def __init__(self, provider_registry: ProviderRegistry):
        self.provider_registry = provider_registry
        self.models_config = provider_registry.get_models_config()
        self.active_subagents = {}
    
    def create_subagent(self, subagent_type: str, task_description: str):
        """Create subagent for specific task"""
        subagent_config = self.models_config.get("subagents", {}).get(subagent_type)
        if not subagent_config:
            raise ValueError(f"Unknown subagent type: {subagent_type}")
        
        # Create subagent using basic agent manager
        from src.agents.basicagents.managers import agent_manager
        
        return agent_manager.create_agent(
            provider=subagent_config["provider"],
            model=subagent_config["model"],
            agent_type="basic"
        )
    
    def get_available_subagents(self) -> List[str]:
        """Get list of available subagent types"""
        return list(self.models_config.get("subagents", {}).keys())
```

## Error Handling

### DeepAgent Error Recovery
```python
class DeepAgentErrorHandler:
    def handle_middleware_error(self, error: Exception, middleware_name: str):
        """Handle middleware errors"""
        logger.error(f"Middleware error in {middleware_name}: {error}")
        
        # Disable problematic middleware
        self._disable_middleware(middleware_name)
        
        # Continue with remaining middleware
        return True
    
    def handle_subagent_error(self, error: Exception, subagent_type: str):
        """Handle subagent errors"""
        logger.error(f"Subagent error in {subagent_type}: {error}")
        
        # Fallback to main agent
        return self._fallback_to_main_agent()
```

## Performance Considerations

### Resource Management
- **Middleware Optimization**: Middleware components are optimized for performance
- **Subagent Pooling**: Subagents are pooled for reuse to reduce creation overhead
- **Memory Management**: Proper cleanup of resources when agents are destroyed

### Scalability
- **Concurrent Subagents**: Support for multiple concurrent subagents
- **Resource Limits**: Configurable limits to prevent resource exhaustion
- **Load Balancing**: Intelligent distribution of tasks across subagents
