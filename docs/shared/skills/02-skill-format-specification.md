# SKILL.md Format Specification

> Based on [Agent Skills Specification](https://agentskills.io/specification) + Claude Code Extensions

## 1. File Structure

Every skill requires exactly one file: `SKILL.md`, located inside a directory whose name matches the skill's `name` field.

```
<skill-name>/
├── SKILL.md           # Required
├── scripts/           # Optional: executable code
├── references/        # Optional: documentation
└── assets/            # Optional: static resources
```

## 2. SKILL.md Anatomy

A SKILL.md file has two parts:

```markdown
---
YAML frontmatter (metadata)
---

Markdown body (instructions)
```

---

## 3. YAML Frontmatter

### 3.1 Required Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `name` | string | 1-64 chars, `[a-z0-9-]`, must match directory name | Unique skill identifier |
| `description` | string | 1-1024 chars | What the skill does and when to use it |

### 3.2 Optional Fields (Agent Skills Spec)

| Field | Type | Constraints | Default | Description |
|-------|------|-------------|---------|-------------|
| `license` | string | - | `null` | License name or reference |
| `compatibility` | string | Max 500 chars | `null` | Environment requirements |
| `metadata` | Dict[str, str] | All values must be strings | `{}` | Arbitrary key-value pairs |
| `allowed-tools` | string | Space-delimited tool names | `[]` | Recommended tools for this skill |

### 3.3 Claude Code Extension Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `user-invocable` | boolean | `true` | Whether users can manually invoke this skill |
| `disable-model-invocation` | boolean | `false` | If `true`, agent won't auto-load this skill |
| `argument-hint` | string | `null` | Hint displayed in autocomplete, e.g. `[topic]` |
| `context` | string | `null` | Set to `"fork"` to run skill as subagent |
| `agent` | string | `null` | Subagent type when `context: fork` |

---

## 4. Name Validation Rules

The `name` field must follow the Agent Skills specification:

```
1. Length: 1-64 characters
2. Characters: lowercase letters (a-z), digits (0-9), hyphens (-)
3. Must NOT start with a hyphen
4. Must NOT end with a hyphen
5. Must NOT contain consecutive hyphens (--)
6. Must match the parent directory name exactly
```

### Examples

```
VALID:
  web-research          OK
  skill-creator         OK
  my-tool-v2            OK
  a                     OK
  code-review-v3        OK

INVALID:
  Web-Research          FAIL (uppercase)
  _private              FAIL (underscore not allowed)
  my--skill             FAIL (consecutive hyphens)
  -start                FAIL (starts with hyphen)
  end-                  FAIL (ends with hyphen)
  my_skill              FAIL (underscore not allowed)
  My Skill              FAIL (spaces and uppercase)
```

### Regex Pattern

```python
SKILL_NAME_PATTERN = r'^[a-z0-9]([a-z0-9]*(-[a-z0-9]+)*)?$'
```

---

## 5. Metadata Field Details

### 5.1 `description`

The description is critical for agent matching. It should answer:
- **What** does this skill do?
- **When** should the agent use it?
- Include **keywords** that help the agent recognize relevant tasks.

```yaml
# Good: specific, includes trigger keywords
description: >
  Guide for creating new skills with proper SKILL.md structure,
  naming conventions, and validation. Use when user asks to
  create, build, or define a custom skill or workflow.

# Bad: too vague
description: A helpful skill for doing things.
```

### 5.2 `metadata`

Arbitrary key-value pairs for additional information. All values must be strings.

```yaml
metadata:
  author: your-team
  version: "1.0.0"
  category: research        # research, coding, meta, general
  tags: "web, search, api"
```

Recommended keys:
- `author`: Creator of the skill
- `version`: Semantic version string
- `category`: Skill category for filtering
- `tags`: Comma-separated keywords

### 5.3 `allowed-tools`

Space-delimited list of tool names the skill recommends using.

```yaml
allowed-tools: read_real_file grep_real_files write_real_file
```

This is informational in Phase 1 (not enforced). Future phases may restrict tool access based on this field.

### 5.4 `compatibility`

Describes environment requirements for the skill to function properly.

```yaml
compatibility: >
  Requires tavily_search tool and Python 3.8+.
  Network access needed for web research.
```

---

## 6. Markdown Body

The body after the YAML frontmatter contains the skill's instructions in Markdown format.

### 6.1 Guidelines

1. **Keep under 500 lines** — Move detailed references to `references/` directory
2. **Be concise** — Claude is already capable; only add knowledge it doesn't have
3. **Use step-by-step workflows** — Numbered steps guide the agent's execution
4. **Include examples** — Show expected inputs and outputs
5. **Specify edge cases** — Document common pitfalls and how to handle them

### 6.2 Recommended Structure

```markdown
---
(frontmatter)
---

# Skill Name

Brief one-line overview.

## When to Use

Describe the scenarios where this skill should be activated.

## Workflow

### Step 1: ...
### Step 2: ...
### Step 3: ...

## Examples

### Example 1: ...

## Edge Cases

- If X happens, do Y
- If Z is unavailable, fallback to W

## References

For detailed API documentation, read `references/api_reference.md`.
```

---

## 7. Supporting Directories

### 7.1 `scripts/`

Executable scripts that the agent can run during skill execution.

```
scripts/
├── search.py           # Python script
├── validate.sh         # Bash script
└── requirements.txt    # Dependencies (informational)
```

Usage in SKILL.md:
```markdown
Run the search script:
\`\`\`
python <skill-path>/scripts/search.py "query"
\`\`\`
```

### 7.2 `references/`

Documentation files loaded on-demand (L3 progressive disclosure).

```
references/
├── api_reference.md    # Detailed API docs
├── examples.md         # Extended examples
└── troubleshooting.md  # Common issues
```

Usage in SKILL.md:
```markdown
For detailed API reference, read `<skill-path>/references/api_reference.md`.
```

### 7.3 `assets/`

Static resources that don't contribute to context.

```
assets/
├── template.json       # Template files
├── schema.json         # JSON schemas
└── diagram.png         # Reference diagrams
```

---

## 8. Complete Example

### File: `~/.iris/skills/web-research/SKILL.md`

```yaml
---
name: web-research
description: >
  Structured methodology for conducting thorough web research.
  Use when user asks to research a topic, find information online,
  or investigate a subject. Guides multi-step research with
  source validation and synthesis.
license: MIT
compatibility: Requires tavily_search or similar web search tool
metadata:
  author: iris-team
  version: "1.0.0"
  category: research
allowed-tools: read_real_file write_real_file tavily_search
---

# Web Research Skill

Conduct thorough, well-sourced web research on any topic.

## When to Use

- User asks to "research", "investigate", or "find out about" a topic
- User needs comprehensive information from multiple sources
- User wants a research report or summary

## Workflow

### Step 1: Plan Research
1. Break the topic into 3-5 specific research questions
2. Identify what types of sources would be most authoritative

### Step 2: Execute Searches
1. For each research question, perform a targeted search
2. Use specific, focused queries rather than broad ones
3. Collect at least 3 sources per question

### Step 3: Validate Sources
1. Check source credibility (official docs, academic, reputable news)
2. Cross-reference claims across multiple sources
3. Note any conflicting information

### Step 4: Synthesize Findings
1. Organize findings by theme, not by source
2. Highlight key insights and patterns
3. Note areas of uncertainty or conflicting information

### Step 5: Present Results
1. Lead with the most important findings
2. Include source citations
3. Suggest areas for further research if applicable

## Edge Cases

- If search tools are unavailable, inform the user and suggest alternatives
- If sources conflict, present both viewpoints with sources
- For rapidly changing topics, note the date of information
```

---

## 9. Validation Checklist

Before publishing a skill, verify:

- [ ] `SKILL.md` exists in the skill directory
- [ ] YAML frontmatter is valid (between `---` delimiters)
- [ ] `name` field matches directory name exactly
- [ ] `name` follows naming rules (lowercase, hyphens, no consecutive hyphens)
- [ ] `description` is non-empty and under 1024 characters
- [ ] SKILL.md body is under 500 lines
- [ ] Instructions are clear and actionable
- [ ] All referenced files (scripts/, references/) actually exist
- [ ] File size is under 10 MB

---

## 10. Anti-Patterns

### Don't: Include information Claude already knows
```markdown
# Bad
Python is a programming language created by Guido van Rossum...
```

### Don't: Write verbose instructions
```markdown
# Bad
First, you should think carefully about the problem.
Then, consider all the different approaches you could take.
After that, weigh the pros and cons of each approach.
Finally, choose the best approach and implement it.
```

### Don't: Duplicate tool documentation
```markdown
# Bad
The read_real_file tool takes a file_path parameter which is...
```

### Do: Add only unique knowledge
```markdown
# Good
## Our Project Conventions
- All API endpoints follow the /api/v{version}/{resource} pattern
- Database migrations must be backward-compatible
- Tests must include both unit and integration coverage
```
