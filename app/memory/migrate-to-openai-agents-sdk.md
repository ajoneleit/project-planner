# Migrate To Openai Agents Sdk Project

## Project Overview

**Project Goal:**  
Migrate from LangChain/LangGraph to the OpenAI Agents SDK with session-based memory, fixing current memory issues and achieving zero-downtime cutover.  

**Current Pain Points:**  
- Markdown-only memory leads to context loss.  
- Weak reference handling.  
- Inefficient load/save processes.  
- Messy threading implementations.  

**Target Architecture:**  
- **Components:** FastAPI (+SSE) → Agents SDK → OpenAI LLM.  
- **Storage:** Hybrid approach using SQLite sessions for conversation history/threading and Markdown for the human-readable project documentation.  

**Phased Plan (Risk-Controlled):**   
1. **Memory Foundation:**  
   - Introduce SQLite sessions, conversation threading, reference resolution, and summarization.  
   - Implement dual-write during the transition.  

2. **SDK Preparation:**  
   - Integrate Agents SDK and validate streaming/observability.  
   - Maintain existing API stability through a compatibility layer.  

3. **Agent Migration:**  
   - Port prompts to two roles:  
     - Chat Agent (leads conversation).  
     - Info Agent (extract/updates documentation).  
   - Implement handoffs and orchestration.  

4. **Testing:**  
   - Conduct unit, integration, and end-to-end testing.  
   - Replay historical transcripts.  
   - Perform performance/load tests, A/B testing, and parallel validation.  
   - Ensure rollback readiness.  

5. **Deployment:**  
   - Utilize blue-green deployment with feature flags.  
   - Stage the ramp-up and migrate historical data.  
   - Keep the legacy system in read-only mode as a fallback.  

6. **Optimization & Monitoring:**  
   - Tune latency and costs.  
   - Strengthen guardrails.  
   - Set up dashboards and alerts for continuous improvements.  

**Success Criteria:**  
- Achieve a seamless transition.  
- Resolve memory continuity/reference context issues.  
- Preserve existing functionality with improved performance and robust operations.  

**Risks & Mitigations:**  
- **Memory corruption:** Addressed via dual-write, backups, and rollback strategies.  
- **SSE quirks:** Early proof of concept and adapter development.  
- **Performance dips:** Mitigated through parallel testing and gradual rollout.

