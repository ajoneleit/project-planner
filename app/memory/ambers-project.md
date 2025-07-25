# Ambers Project
_Last updated: 2025-07-25 16:34:08_

---

## Executive Summary
Project documentation is being developed through conversation with the AI assistant.

---

## Objective
Success will be indicated by the ability to fully develop projects accurately without human intervention. The system will work by having a meta-agent dynamically allocate tasks to sub-agents, which will perform their tasks. The code generated will be verified by a compiler and accompanied by generated tests. If any verification stage fails, a message will be sent to the meta-agent to resolve the error by creating new subtasks to fix the issue. This loop will continue until there are no errors.

---

## Context
This project aims to develop an advanced multiagentic coding system that will revolutionize how NAI develops software applications.

The system will enable developers to create applications using simple natural language prompts, reducing development time and complexity.

The solution will benefit the entire NAI organization by democratizing application development capabilities.

---

## Glossary
| Term | Definition | Added by |
|------|------------|----------|
| Meta-Agent | Central coordinating agent that manages other specialized agents | User |
| Sub-Agents | Specialized agents including Architect, Builder, Validator, and Scribe | User |
| Validator | Agent that runs compilation and tests | User |

---

## Constraints & Risks
- Token limits were added to the constraints and risks section on 2025-07-25.

---

## Stakeholders & Collaborators
Add names, roles, departments, responsibilities, and contact information of users or stakeholders.

---

## Systems & Data Sources
- **Orchestration Language**: Python 3.9+ (asyncio) - Drives meta-agent, sub-agent manager, task scheduler.
- **Performance Kernels**: Rust (zero-engine crate) - Hot-path computation & parallelism; called from Python via FFI.
- **Large-Language Models**:
  - OpenAI o3 / GPT-4 – meta-agent reasoning.
  - Anthropic Claude Code CLI – code-generation sub-agents.
- **Prompt / Template Engine**: Custom PromptTemplate class (Jinja-style) - All prompt files live under `src/prompts/`.
- **Build & CI**: GitHub Actions (matrix 3.9-3.12) - Lint → tests → coverage → static/security scan → quality gate.
- **Quality Tooling**:
  - Pytest + pytest-cov (coverage.xml).
  - Pylint (JSON output).
  - Bandit / Safety (security).
  - Cargo (clippy, test) for Rust - Parsed by `scripts/enforce_quality.py`.
- **Artifact & Memory Store**: Local filesystem under `artifacts/` and `memory/` - Versioning + JSON index; no external DB yet.
- **Message Bus**: JSON files in `memory/projects/{id}/messages/` - Simpler than Redis/Kafka; keeps runtime Docker-free.
- **Documentation / Validation**: Markdown in `/docs/` + custom validators (`doc_validator.py`, `reality_checker.py`) - CI blocks on doc-vs-code drift.
- **Metrics & Dashboard (Planned Phase 3)**: Static HTML + generated JSON metrics (no live DB) - Shows pass-rate, iteration count, cost/run.
- **Dev Environment**: venv + `requirements.txt` + pre-commit hooks - Pre-commit runs quality gates locally.

---

## Attachments & Examples

| Item | Type | Location | Notes |
|------|------|----------|-------|

---

## Open Questions & Conflicts

| Question/Conflict | Owner | Priority | Status |
|-------------------|-------|----------|--------|

---

## Next Actions
| When | Action | Why it matters | Owner |
|------|--------|----------------|-------|
| Today | Run a clean-clone CI test | Proves the pipeline really passes on a fresh repo and that quality reports are generated | Amber / DevOps |
| Today | Confirm reports/coverage.xml & reports/pylint.json show up as artifacts | Proves the pipeline really passes on a fresh repo and that quality reports are generated | Amber / DevOps |
| Today | Commit the first artifacts/baseline_<date>/ folder with coverage & pylint summaries | Locks in a baseline before fixes; the quality-gate script will compare against this | Amber |
| Today | Add Reality-Score badge to the README (pulls from nightly report) | Gives everyone an at-a-glance signal when docs drift from code | Amber |

---

## Recent Discussions
**2025-07-25 16:34**: Hello, test message from user

---

## Change Log

| Date | Contributor | Summary |
|------|-------------|---------|
| 2025-07-25 16:34:08 | Test User | user_3 | Updated Recent Discussions |
| 2025-07-25 15:33:14 | Anonymous User | anonymous | Updated Constraints & Risks |
| 2025-07-25 15:32:10 | Anonymous User | anonymous | Updated Constraints & Risks |
| 2025-07-25 15:24:21 | Anonymous User | anonymous | Updated Constraints & Risks |
| 2025-07-25 15:22:33 | Anonymous User | anonymous | Updated Stakeholders & Collaborators |
| 2025-07-25 15:22:16 | Anonymous User | anonymous | Updated Constraints & Risks |
| 2025-07-25 14:16:38 | User | Updated Constraints & Risks |
| 2025-07-25 14:15:22 | User | Updated Objective |
| 2025-07-25 11:17:24 | User | Updated Next Actions |
| 2025-07-25 11:17:21 | User | Updated Objective |
| 2025-07-25 11:15:42 | User | Updated Constraints & Risks |
| 2025-07-25 11:15:39 | User | Updated Stakeholders & Collaborators |
| 2025-07-25 11:15:37 | User | Updated Objective |
| 2025-07-25 11:15:15 | User | Updated Recent Discussions |
| 2025-07-25 11:13:35 | User | Updated Systems & Data Sources |
| 2025-07-25 11:12:56 | User | Updated Recent Discussions |
| 2025-07-25 11:06:38 | User | Updated Next Actions |
| 2025-07-25 11:06:35 | User | Updated Systems & Data Sources |
| 2025-07-25 08:53:58 | User | Updated Glossary |
| 2025-07-25 08:53:54 | User | Updated Systems & Data Sources |
| 2025-07-25 08:49:53 | User | Updated Glossary |
| 2025-07-25 08:49:49 | User | Updated Systems & Data Sources |
| 2025-07-25 08:22:32 | User | Updated Glossary |
| 2025-07-24 17:47:33 | User | Updated Stakeholders & Collaborators |
| 2025-07-24 17:36:19 | User | Updated Glossary |
| 2025-07-24 17:36:19 | User | Updated Next Actions |
| 2025-07-24 17:36:19 | User | Updated Systems & Data Sources |
| 2025-07-24 17:36:19 | User | Updated Context |
| 2025-07-24 17:36:19 | User | Updated Objective |
| 2025-07-24 17:36:19 | User | Updated Stakeholders & Collaborators |
| 2025-07-24 16:14:18 | User | Updated Glossary |
| 2025-07-24 16:14:18 | User | Updated Systems & Data Sources |
| 2025-07-24 16:10:41 | User | Updated Glossary |
| 2025-07-24 16:10:41 | User | Updated Next Actions |
| 2025-07-24 16:10:41 | User | Updated Systems & Data Sources |
| 2025-07-24 16:10:41 | User | Updated Context |
| 2025-07-24 16:10:41 | User | Updated Objective |
| 2025-07-24 16:10:41 | User | Updated Stakeholders & Collaborators |
| 2025-07-24 16:10:41 | System | Initial structured project document created |

