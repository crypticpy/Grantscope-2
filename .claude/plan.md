# Implementation Plan: Autonomous GPT Researcher Azure OpenAI Debugging

Created: 2025-12-27
Status: PENDING APPROVAL

## Summary
Autonomously debug and fix the GPT Researcher Azure OpenAI integration that's returning `LLM Response: None`. This plan enables Claude to test the debug endpoint, analyze the configuration, identify the root cause, and implement a fix - all without user intervention.

## Scope
### In Scope
- Wait for Railway to deploy the debug endpoint
- Hit the debug endpoint and analyze the JSON response
- Identify the exact misconfiguration in GPT Researcher's Azure setup
- Fix the configuration issue (either env var format or code-level fix)
- Verify the fix works by testing research functionality
- Document findings for the user to review when they wake up

### Out of Scope
- Changing Azure OpenAI deployments or keys (those are confirmed working)
- Modifying the core GPT Researcher library
- Frontend changes

## Prerequisites
- Railway deployment of commit `3107ab9` (the debug endpoint)
- All Azure OpenAI env vars already configured in Railway (confirmed by user)

## Parallel Execution Strategy
This is primarily a sequential debugging task, but Phase 2 can parallelize analysis work.

### Workstream Analysis
| Workstream | Agent Type | Files Owned | Dependencies |
|------------|------------|-------------|--------------|
| Debug Analysis | debugger-detective | None (read-only) | Debug endpoint response |
| Fix Implementation | backend-engineer | backend/app/research_service.py | Analysis results |
| Verification | quality-engineer | None (testing) | Fix deployed |

### File Ownership Matrix
| File | Phase 1 | Phase 2 | Phase 3 |
|------|---------|---------|---------|
| backend/app/main.py | - | Fix if needed | - |
| backend/app/research_service.py | - | Fix if needed | - |
| backend/.env.example | - | Update docs | - |

## Implementation Phases

### Phase 1: Verify Deployment & Gather Debug Data
**Objective**: Confirm the debug endpoint is deployed and capture the diagnostic output

**Sequential Tasks**:
1. **Wait for Railway deployment** - Check every 30 seconds for up to 5 minutes
2. **Hit the debug endpoint** - Use WebFetch to call `/api/v1/debug/gpt-researcher`
3. **Capture and analyze the JSON response**:
   - `env_vars`: What GPT Researcher sees
   - `gptr_config.parsed`: How GPT Researcher parsed the config
   - `langchain_azure_test`: Whether LangChain can connect to Azure

**Verification**:
- [ ] Debug endpoint returns 200 with JSON (not 404)
- [ ] All three diagnostic sections are present

**Expected Findings**:
Based on previous logs, likely issues:
- `SMART_LLM`/`FAST_LLM` might be missing the `azure_openai:` prefix
- `OPENAI_API_VERSION` might be incompatible (2025 vs 2024)
- LangChain might be failing to authenticate

### Phase 2: Root Cause Analysis & Fix
**Objective**: Identify exact failure point and implement fix

**Analysis Decision Tree**:
```
IF langchain_azure_test.status == "error":
    → Azure connection failing (API version, endpoint, or auth issue)
    → Check langchain_azure_test.error for details

ELIF langchain_azure_test.status == "success" BUT gptr_config.parsed shows wrong values:
    → GPT Researcher config parsing issue
    → Check env var format (azure_openai:deployment-name)

ELIF both work BUT research still fails:
    → Issue is in how research_service.py initializes GPTResearcher
    → May need to pass config explicitly instead of relying on env vars
```

**Potential Fixes** (implement based on analysis):

1. **If env var format is wrong**:
   - Document correct format for user
   - Update `.env.example` with correct GPT Researcher format

2. **If LangChain auth fails**:
   - Check if `OPENAI_API_VERSION` needs to be `2024-05-01-preview`
   - Verify endpoint format

3. **If GPT Researcher needs explicit config**:
   - Modify `research_service.py` to pass LLM config directly to GPTResearcher:
   ```python
   from gpt_researcher.config import Config

   config = Config()
   config.llm_provider = "azure_openai"
   config.fast_llm_model = os.getenv("AZURE_OPENAI_DEPLOYMENT_CHAT_MINI")
   config.smart_llm_model = os.getenv("AZURE_OPENAI_DEPLOYMENT_CHAT")

   researcher = GPTResearcher(query=query, config=config)
   ```

**Files to Modify** (if needed):
- `backend/app/research_service.py:241-245` - GPTResearcher initialization
- `backend/.env.example` - Document correct env var format

### Phase 3: Verification & Documentation
**Objective**: Confirm fix works and document for user

**Tasks**:
1. Push fix to GitHub (triggers Railway deploy)
2. Wait for deployment
3. Test research endpoint OR check Railway logs for success
4. Create summary document for user

**Verification**:
- [ ] Research returns >0 sources
- [ ] No `LLM Response: None` in logs
- [ ] GPT Researcher successfully queries web and generates report

**Documentation Deliverable**:
Create `/Users/aiml/Projects/foresight-app/GPT-RESEARCHER-FIX-SUMMARY.md` with:
- What was wrong
- What was fixed
- How to verify it works
- Any remaining issues

## Testing Strategy
1. **Debug Endpoint Test**: WebFetch to `/api/v1/debug/gpt-researcher`
2. **Logs Check**: Monitor Railway logs after fix deployment
3. **Functional Test**: If possible, trigger research via API

## Rollback Plan
- Revert commit if fix breaks something: `git revert HEAD`
- Debug endpoint can be removed after fix is confirmed

## Risks and Mitigations
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Railway deployment slow | Med | Low | Wait with timeout, retry |
| Can't access Railway logs | Low | Med | Use debug endpoint output |
| Fix requires user env var changes | Med | Med | Document clearly in summary |
| LangChain version incompatibility | Low | High | Check library versions, document workaround |

## Open Questions
None - all env vars are confirmed set by user. This is an autonomous debugging session.

## Execution Timeline
- Phase 1: 5-10 minutes (waiting for deployment)
- Phase 2: 10-20 minutes (analysis and fix)
- Phase 3: 5-10 minutes (verification and docs)
- Total: ~30-40 minutes

---
**USER: Please review this plan. You mentioned you need to sleep - I will execute this autonomously and document findings. Confirm to proceed, or just go to sleep and I'll continue.**
