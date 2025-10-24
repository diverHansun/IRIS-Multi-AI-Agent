# DeepAgents Prompts

## Overview

DeepAgents prompt system provides specialized prompts for main agents and subagents, supporting variable substitution and multi-language support. The system is designed for function-specific prompts rather than provider-specific prompts.

## Architecture

### Directory Structure
```
src/components/deepagents/prompts/
├── __init__.py
├── registry.py           # Prompt registry and management
├── main_agent.md         # Main agent prompt template
└── subagents/
    ├── research.md       # Research subagent prompt
    ├── coding.md         # Coding subagent prompt
    └── analysis.md       # Analysis subagent prompt
```

### Prompt Registry
```python
# src/components/deepagents/prompts/registry.py
class DeepAgentPromptRegistry:
    def __init__(self, prompts_dir: str = "src/components/deepagents/prompts"):
        self.prompts_dir = Path(prompts_dir)
        self._cached_prompts = {}
    
    def get_main_agent_prompt(self, **kwargs) -> str:
        """Get main agent prompt with variable substitution"""
        template = self._load_template("main_agent.md")
        return self._substitute_variables(template, kwargs)
    
    def get_subagent_prompt(self, subagent_type: str, **kwargs) -> str:
        """Get subagent prompt with variable substitution"""
        template = self._load_template(f"subagents/{subagent_type}.md")
        return self._substitute_variables(template, kwargs)
    
    def _substitute_variables(self, template: str, variables: Dict[str, Any]) -> str:
        """Substitute variables in template"""
        return template.format(**variables)
```

## Prompt Templates

### Main Agent Prompt
```markdown
# Main Agent Prompt Template

You are a Deep Agent capable of coordinating multiple specialized subagents to complete complex tasks.

## Available Subagents
{subagents_list}

## Task Coordination
- Analyze the user's request and determine which subagents are needed
- Break down complex tasks into manageable sub-tasks
- Coordinate subagent execution and synthesize results
- Provide clear, comprehensive responses to users

## Subagent Usage Guidelines
- Use research agents for information gathering and analysis
- Use coding agents for programming and technical tasks
- Use analysis agents for data processing and reporting
- Coordinate multiple subagents for complex multi-step tasks

## Response Format
Always provide clear explanations of your reasoning and the steps taken to complete the task.
```

### Research Subagent Prompt
```markdown
# Research Subagent Prompt

You are a dedicated research specialist. Your role is to conduct thorough research on assigned topics and provide comprehensive, well-sourced information.

## Research Guidelines
- Use multiple sources to verify information
- Provide citations and references when possible
- Focus on accuracy and completeness
- Organize findings in a clear, logical structure

## Research Process
1. Identify key research questions
2. Gather information from multiple sources
3. Analyze and synthesize findings
4. Present results in a structured format

## Output Format
Provide a comprehensive research report with:
- Executive summary
- Detailed findings
- Sources and references
- Recommendations or conclusions
```

### Coding Subagent Prompt
```markdown
# Coding Subagent Prompt

You are a specialized coding assistant. Your role is to help with programming tasks, code analysis, and technical problem-solving.

## Coding Guidelines
- Write clean, well-documented code
- Follow best practices and coding standards
- Provide explanations for complex logic
- Test and validate solutions

## Task Types
- Code generation and modification
- Bug fixing and debugging
- Code review and optimization
- Technical documentation

## Output Format
Provide:
- Working code solutions
- Clear explanations
- Testing recommendations
- Documentation when needed
```

### Analysis Subagent Prompt
```markdown
# Analysis Subagent Prompt

You are a data analysis specialist. Your role is to analyze data, generate insights, and create reports.

## Analysis Guidelines
- Use appropriate analytical methods
- Provide clear interpretations
- Support conclusions with data
- Present findings visually when helpful

## Analysis Process
1. Understand the data and requirements
2. Choose appropriate analytical methods
3. Perform analysis and generate insights
4. Create clear, actionable reports

## Output Format
Provide:
- Analysis methodology
- Key findings and insights
- Visual representations when appropriate
- Actionable recommendations
```

## Variable Substitution

### Supported Variables
- `{subagents_list}`: List of available subagents
- `{tools_list}`: List of available tools
- `{task_description}`: Current task description
- `{user_context}`: User context information

### Variable Usage
```python
# Example variable substitution
prompt = registry.get_main_agent_prompt(
    subagents_list="research, coding, analysis",
    tools_list="internet_search, file_read, code_analysis",
    task_description="Analyze market trends and create a report"
)
```

## Integration

### With Adapters
```python
# src/agents/deepagents/adapters/research_adapter.py
class ResearchAdapter(BaseDeepAgentAdapter):
    def _get_research_prompt(self) -> str:
        """Load research-specific prompt"""
        from src.components.deepagents.prompts.registry import DeepAgentPromptRegistry
        registry = DeepAgentPromptRegistry()
        return registry.get_subagent_prompt("research")
```

### With Factories
```python
# src/agents/deepagents/factories/research_factory.py
class ResearchFactory(BaseDeepAgentFactory):
    def create_agent(self, provider: str, model: str):
        adapter = ResearchAdapter(provider, model)
        config = adapter.get_agent_config()
        
        # Use prompt from adapter
        system_prompt = config["system_prompt"]
        
        return ResearchAgent(
            adapter=adapter,
            system_prompt=system_prompt
        )
```

## Configuration

### Prompt Configuration
```json
{
  "prompts": {
    "main_agent": {
      "template": "main_agent.md",
      "variables": ["subagents_list", "tools_list"]
    },
    "subagents": {
      "research": {
        "template": "subagents/research.md",
        "variables": ["task_description", "user_context"]
      },
      "coding": {
        "template": "subagents/coding.md",
        "variables": ["task_description", "code_context"]
      },
      "analysis": {
        "template": "subagents/analysis.md",
        "variables": ["data_context", "analysis_requirements"]
      }
    }
  }
}
```

## Error Handling

### Template Loading Errors
```python
class PromptError(Exception):
    """Base class for prompt-related errors"""
    pass

class TemplateNotFoundError(PromptError):
    """Template file not found"""
    pass

class VariableSubstitutionError(PromptError):
    """Variable substitution failed"""
    pass
```

### Error Recovery
```python
def _load_template(self, template_path: str) -> str:
    """Load template with error handling"""
    try:
        full_path = self.prompts_dir / template_path
        return full_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        logger.error(f"Template not found: {template_path}")
        return self._get_default_template(template_path)
    except Exception as e:
        logger.error(f"Error loading template {template_path}: {e}")
        raise TemplateNotFoundError(f"Failed to load template: {template_path}")
```

## Performance Considerations

### Caching
- **Template Caching**: Templates are cached in memory to avoid repeated file reads
- **Variable Caching**: Frequently used variable substitutions are cached
- **Lazy Loading**: Templates are loaded only when needed

### Optimization
- **Template Preprocessing**: Templates are preprocessed for common variables
- **Variable Validation**: Variables are validated before substitution
- **Memory Management**: Unused templates are removed from cache
