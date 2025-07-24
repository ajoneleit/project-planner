# Custom Prompt System Documentation

## Overview

The Project Planner Bot uses a custom prompt system that tracks prompts in Git for version control and observability. This document outlines how the system works and how to manage prompts effectively.

## System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Git Prompts   │───►│   LangGraph      │───►│   LangSmith     │
│   (prompts/)    │    │   Runner         │    │   Tracing       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Version       │    │   Conversation   │    │   Performance   │
│   Control       │    │   Memory         │    │   Analytics     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Prompt Structure

### Location
All system prompts are stored in the `prompts/` directory:
```
prompts/
├── project_planner.md     # Main system prompt
├── specialized/           # Task-specific prompts
│   ├── analysis.md
│   ├── code_review.md
│   └── planning.md
└── templates/             # Reusable prompt templates
    ├── conversation.md
    └── memory.md
```

### Format
Prompts use Markdown format with structured sections:

```markdown
# Prompt Title

## Context
Brief description of when this prompt is used.

## Instructions
Clear, actionable instructions for the AI.

## Examples
Concrete examples of expected behavior.

## Constraints
Limitations and boundaries.

## Metadata
- Version: 1.0.0
- Last Updated: 2024-01-XX
- Author: Team/Individual
- Tags: planning, analysis, conversation
```

## Version Control Integration

### Git Tracking
- All prompts are tracked in Git alongside code changes
- Prompt versions correspond to Git commits/tags
- Changes are reviewable through pull requests
- History provides audit trail for prompt evolution

### Versioning Strategy
- **Major versions** (2.0.0): Fundamental prompt restructuring
- **Minor versions** (1.1.0): New capabilities or significant improvements
- **Patch versions** (1.0.1): Bug fixes, clarifications, minor tweaks

### Branch Strategy
- `main`: Production prompts
- `develop`: Integration testing
- `feature/prompt-*`: Prompt development branches

## LangSmith Integration

### Automatic Tracking
The system automatically tracks:
- Prompt content and version for each conversation
- Model responses and quality metrics
- User feedback and ratings
- Performance analytics (latency, token usage)

### Metadata Injection
Each LangGraph run includes:
```json
{
  "prompt_version": "project_planner_v1.2.0",
  "prompt_hash": "sha256:abc123...",
  "git_commit": "f6ad9c3",
  "timestamp": "2024-01-XX",
  "environment": "production"
}
```

### Observability Benefits
- **A/B Testing**: Compare prompt versions side-by-side
- **Performance Monitoring**: Track quality metrics over time
- **Debug Tracing**: Correlate issues with specific prompt versions
- **Cost Analysis**: Understand token usage patterns

## Development Workflow

### 1. Local Development
```bash
# Edit prompts locally
vim prompts/project_planner.md

# Test with development environment
docker-compose up

# Verify changes work correctly
curl -X POST http://localhost:8000/api/projects/test-project/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Test message"}'
```

### 2. Testing & Validation
```bash
# Run tests with new prompts
pytest tests/ -v

# Check prompt formatting
python scripts/validate_prompts.py

# Review LangSmith traces
# Visit https://smith.langchain.com/projects/planner-bot-dev
```

### 3. Deployment Process
```bash
# Create feature branch
git checkout -b feature/prompt-improvements

# Make changes and commit
git add prompts/
git commit -m "Improve project planning prompt clarity"

# Push and create PR
git push origin feature/prompt-improvements
gh pr create --title "Improve prompt clarity" --body "Detailed description"

# After review and merge
git checkout main
git pull origin main

# Deploy triggers automatic CI/CD
# Prompts are deployed with application code
```

## Best Practices

### Writing Effective Prompts
1. **Be Specific**: Clear, unambiguous instructions
2. **Provide Context**: Explain the purpose and environment
3. **Include Examples**: Show expected input/output patterns
4. **Set Boundaries**: Define what the AI should and shouldn't do
5. **Use Structure**: Organize with headers and bullet points

### Version Management
1. **Semantic Versioning**: Follow semver for prompt versions
2. **Changelog**: Document what changed and why
3. **Backward Compatibility**: Consider impact on existing conversations
4. **Testing**: Validate changes don't break existing functionality

### Observability
1. **Tag Strategically**: Use meaningful tags for filtering
2. **Monitor Metrics**: Track quality, latency, and cost
3. **Analyze Patterns**: Look for common failure modes
4. **Iterate Based on Data**: Use LangSmith insights for improvements

## Monitoring & Analytics

### Key Metrics
- **Quality Score**: User ratings and feedback
- **Latency**: Response time per prompt type
- **Token Usage**: Cost analysis by prompt version
- **Error Rate**: Failed conversations or edge cases
- **User Satisfaction**: Engagement and completion rates

### Alerting
Set up alerts for:
- Quality score drops below threshold
- Latency increases significantly
- Error rate spikes
- Token usage exceeds budget

### Dashboards
Create visualizations for:
- Prompt performance over time
- Version comparison metrics
- User behavior patterns
- Cost attribution by prompt type

## Troubleshooting

### Common Issues
1. **Prompt Not Loading**: Check file path and syntax
2. **Version Mismatch**: Ensure Git commit matches deployed version
3. **Poor Quality**: Review LangSmith traces for failure patterns
4. **High Costs**: Analyze token usage and optimize prompt length

### Debug Commands
```bash
# Check current prompt version
curl http://localhost:8000/health

# View LangSmith traces
curl http://localhost:8000/api/observability/metrics

# Validate prompt syntax
python -c "import yaml; yaml.safe_load(open('prompts/project_planner.md'))"
```

### Support Resources
- **LangSmith Dashboard**: https://smith.langchain.com/
- **Git History**: `git log --oneline prompts/`
- **CloudWatch Logs**: AWS Console → CloudWatch → Log Groups
- **Team Documentation**: Internal wiki and Slack channels

## Migration Guide

### From Legacy System
1. Export existing prompts to Markdown format
2. Add version metadata and structure
3. Commit to Git with proper history
4. Update application to use new prompt system
5. Verify LangSmith integration works
6. Monitor for any regressions

### Between Versions
1. Review changelog for breaking changes
2. Test in development environment first
3. Use feature flags for gradual rollout
4. Monitor quality metrics closely
5. Have rollback plan ready
6. Document any configuration changes needed

---

**Last Updated**: January 2024  
**Version**: 1.0.0  
**Maintainer**: Development Team