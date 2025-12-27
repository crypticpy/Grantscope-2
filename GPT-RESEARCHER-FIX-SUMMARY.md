# GPT Researcher Azure OpenAI Fix Summary

**Date**: December 27, 2025
**Status**: FIX UPDATED - READY TO DEPLOY
**Commits**: See latest git history

---

## Problem

GPT Researcher was returning `LLM Response: None` causing research to fail with 0 sources discovered.

## Root Causes

### 1) Env var translation (Azure OpenAI)

GPT Researcher requires specific environment variable formats that differ from our app's configuration:

| Our App Uses | GPT Researcher Expects |
|--------------|------------------------|
| `AZURE_OPENAI_KEY` | `AZURE_OPENAI_API_KEY` |
| `AZURE_OPENAI_API_VERSION` | `OPENAI_API_VERSION` |
| `AZURE_OPENAI_DEPLOYMENT_CHAT=gpt-41` | `SMART_LLM=azure_openai:gpt-41` |
| `AZURE_OPENAI_DEPLOYMENT_CHAT_MINI=gpt-41-mini` | `FAST_LLM=azure_openai:gpt-41-mini` |

The critical missing piece was the **`azure_openai:` prefix** in the SMART_LLM and FAST_LLM values.

---

### 2) Passing unsupported `scraper=` kwarg into GPTResearcher

In `backend/app/research_service.py` we were instantiating GPT Researcher like:

```py
GPTResearcher(..., scraper="firecrawl")
```

However, in current GPT Researcher versions (e.g. `0.14.x`), `GPTResearcher.__init__` does **not** accept a `scraper` parameter. Extra kwargs are stored and then forwarded into internal LLM calls, which can break AzureChatOpenAI/OpenAI requests with "unknown parameter" errors.

This manifests as:
- `LLM Response: None`
- `Error in reading JSON ... NoneType`
- `expected string or bytes-like object, got 'NoneType'`

---

## Solutions Implemented

Added `_configure_gpt_researcher_for_azure()` function in `backend/app/research_service.py` that:

1. Reads our app's Azure config (AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT_CHAT, etc.)
2. Translates to GPT Researcher's expected format (SMART_LLM=azure_openai:gpt-41, etc.)
3. Sets the env vars correctly at module load time, BEFORE GPTResearcher is initialized
4. Also sets `AZURE_OPENAI_API_VERSION` because GPT Researcher embeddings read it directly

Updated GPT Researcher initialization to:
- **Stop passing `scraper=` kwarg** (prevents forwarding into LLM calls)
- Configure scraper via env (`SCRAPER=firecrawl` or `SCRAPER=bs`) instead

**Files Modified**:
- `backend/app/research_service.py` - Added auto-config function
- `backend/.env.example` - Documented the translation

---

## Railway Deployment Issue

**Problem**: Railway is not auto-deploying git pushes.

Three commits have been pushed but the production app is still running old code:
- `ef2c6c9` - Debug endpoint (Dec 27)
- `606312a` - GPT Researcher fix (Dec 27)

**Verification**: The debug endpoint at `/api/v1/debug/gpt-researcher` returns 404, confirming old code is running.

---

## Action Required

### Step 1: Manually Trigger Railway Deploy

1. Go to Railway dashboard
2. Select the `foresight-api` service
3. Go to **Deployments** tab
4. Click **Redeploy** on the latest commit (`606312a`)
5. Wait for build to complete (~2-3 min)

### Step 2: Verify Debug Endpoint

After deploy, hit:
```
https://foresight-api-production.up.railway.app/api/v1/debug/gpt-researcher
```

Expected response (if fix works):
```json
{
  "env_vars": {
    "SMART_LLM": "azure_openai:gpt-41",
    "FAST_LLM": "azure_openai:gpt-41-mini",
    ...
  },
  "langchain_azure_test": {
    "status": "success",
    "response": "Hello"
  }
}
```

### Step 3: Test Research

1. Go to the frontend
2. Open any card
3. Click "Research" or "Update"
4. Check Railway logs - should see:
   - `GPT Researcher configured for Azure OpenAI: SMART_LLM=azure_openai:gpt-41...`
   - No more `LLM Response: None` errors
   - Sources being discovered

---

## If Fix Doesn't Work

Check Railway logs for the exact error. Possible issues:

1. **API Version**: If you see auth errors, try changing `AZURE_OPENAI_API_VERSION` in Railway to `2024-05-01-preview`

2. **Deployment Names**: Verify your Azure deployments are actually named `gpt-41` and `gpt-41-mini`. If different, update:
   - `AZURE_OPENAI_DEPLOYMENT_CHAT=<your-gpt4-deployment>`
   - `AZURE_OPENAI_DEPLOYMENT_CHAT_MINI=<your-gpt4-mini-deployment>`

3. **Missing Tavily Key**: GPT Researcher also needs `TAVILY_API_KEY` for web search

---

## Rollback

If this fix causes issues:
```bash
git revert 606312a
git push
```

---

## Technical Details

The fix works by setting env vars at Python module load time:

```python
def _configure_gpt_researcher_for_azure():
    # Read our config
    chat_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_CHAT", "gpt-41")

    # Set GPT Researcher format with azure_openai: prefix
    os.environ["SMART_LLM"] = f"azure_openai:{chat_deployment}"
    os.environ["FAST_LLM"] = f"azure_openai:{chat_mini_deployment}"
    os.environ["EMBEDDING"] = f"azure_openai:{embedding_deployment}"
    # ... etc

# Called when research_service.py is imported
_configure_gpt_researcher_for_azure()
```

This ensures GPT Researcher sees the correctly formatted env vars regardless of what was set in Railway.
