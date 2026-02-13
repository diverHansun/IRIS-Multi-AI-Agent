---
name: skill-creator
description: >
  Guide for creating new skills with proper SKILL.md structure,
  naming conventions, and validation rules. Use when the user asks
  to create, update, or design a custom skill workflow.
metadata:
  author: iris-team
  version: "1.0.0"
  category: meta
allowed-tools: read_real_file write_real_file list_real_files
---

# Skill Creator

Use this skill when the user wants to create or improve a `SKILL.md` package.

## Workflow

### Step 1: Confirm use case
1. Clarify the exact tasks the skill should cover.
2. Identify trigger phrases that should appear in `description`.

### Step 2: Create structure
1. Ensure skill directory name matches `name`.
2. Create `SKILL.md` with YAML frontmatter and markdown body.
3. Add `scripts/`, `references/`, `assets/` only if needed.

### Step 3: Validate core fields
1. Validate `name` format: lowercase, digits, hyphens.
2. Ensure `description` clearly states what and when.
3. Keep instructions actionable and concise.

### Step 4: Add implementation guidance
1. Prefer step-by-step procedures.
2. Add edge cases and fallback behavior.
3. Keep long references in `references/` files.

### Step 5: Final checklist
1. Frontmatter parses as valid YAML.
2. `name` equals folder name.
3. Referenced files actually exist.

## Edge Cases

- If the user provides a non-compliant name, suggest a compliant variant.
- If the instructions are too generic, ask for project-specific conventions.
