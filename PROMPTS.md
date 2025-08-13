# System Prompts

## Overview

The Project Planner Bot uses file-based system prompts stored in the `prompts/` directory for version control and easy maintenance.

## Prompt Files

| File | Purpose | Used By |
|------|---------|---------|
| `conversational_nai_agent.md` | Main conversational agent prompt | ConversationAgent |
| `info_agent.md` | Information extraction agent prompt | ProjectAgent |
| `project_planner.md` | Base project planning prompt | Legacy (kept for reference) |

## Usage

Prompts are loaded dynamically from the `prompts/` directory:

```python
# Example from langgraph_runner.py
combined_prompt_file = Path("prompts/conversational_nai_agent.md")
if combined_prompt_file.exists():
    async with aiofiles.open(combined_prompt_file, 'r', encoding='utf-8') as f:
        base_prompt = await f.read()
```

## Editing Prompts

1. **Edit the markdown files** in `prompts/` directory
2. **Test changes** by running the application locally
3. **Deploy** - prompts are automatically included in Docker builds

## Integration

- Prompts are **version controlled** with the codebase
- **LangSmith tracing** automatically captures prompt versions
- **No restart required** - prompts are loaded on each request
- **Fallback handling** - system continues with default prompts if files are missing

## Best Practices

- Use clear, specific instructions
- Include examples when helpful  
- Test changes thoroughly before deployment
- Keep prompts focused on their specific role