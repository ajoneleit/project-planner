# Demo Project

**Created:** 2024-01-01 12:00:00
**Status:** Active
**Type:** Sample Project

## Project Overview
This is a sample project to demonstrate the Project Planner Bot functionality.

## Goals
- Demonstrate conversation flow
- Show markdown memory persistence
- Test the chat interface

## Conversation History

### Q: What is this project about?
**A:** This is a demo project created to showcase how the Project Planner Bot works. It maintains conversation history in markdown files and helps users plan and track projects through natural conversation.

The system uses:
- FastAPI backend with LangGraph
- OpenAI language models
- Markdown files for persistent memory
- Next.js frontend for the chat interface

### Q: How does the memory system work?
**A:** The memory system stores each project's conversation history in individual markdown files within the repository. This approach provides:

1. **Version Control**: All project history is tracked in Git
2. **Human Readable**: Markdown format is easily readable and editable
3. **Structured Data**: Consistent format for questions and answers
4. **Persistence**: Data survives container restarts and deployments

Each project gets its own `.md` file, and the system appends new Q&A pairs as conversations progress.

### Q: Can you help me plan a new feature?
**A:** Absolutely! I can help you break down any feature into manageable tasks. Here's my typical approach:

**Analysis Phase:**
- Understand the feature requirements and user needs
- Identify dependencies and integration points
- Assess technical complexity and risks

**Planning Phase:**
- Break down into smaller, testable components
- Create development timeline with milestones
- Identify required resources and skills

**Implementation Strategy:**
- Suggest development methodology (Agile, iterative, etc.)
- Recommend testing approach
- Plan deployment and rollout strategy

What feature would you like to plan? Please describe your goals and any constraints you're working with.