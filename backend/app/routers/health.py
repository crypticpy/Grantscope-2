"""Health-check and debug router."""

import os
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/")
async def root():
    """Health check"""
    return {"status": "ok", "message": "GrantScope2 API is running"}


@router.get("/api/v1/health")
async def health_check():
    """Detailed health check with search provider and degradation status."""
    from ..search_provider import get_provider_info

    search_info = get_provider_info()

    # Determine capability level based on available services
    capabilities = []
    degraded = []

    # Core: Azure OpenAI (required for AI features)
    if os.getenv("AZURE_OPENAI_API_KEY"):
        capabilities.append("ai_analysis")
    else:
        degraded.append("ai_analysis")

    # Search provider
    if search_info["available"]:
        capabilities.append(f"search:{search_info['provider']}")
    else:
        degraded.append("search")

    # RSS feeds (always available if DB is up)
    capabilities.append("rss_feeds")

    # Crawl4AI (always available, no API key needed)
    capabilities.append("web_crawling")

    # Optional paid API fallbacks
    if os.getenv("TAVILY_API_KEY"):
        capabilities.append("tavily")
    if os.getenv("SERPER_API_KEY"):
        capabilities.append("serper")

    # Grant opportunity integrations
    capabilities.append("grants_gov_integration")
    if os.getenv("SAM_GOV_API_KEY"):
        capabilities.append("sam_gov_integration")

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "database": "connected",
            "ai": "available" if "ai_analysis" in capabilities else "unavailable",
            "search": search_info,
        },
        "capabilities": capabilities,
        "degraded": degraded if degraded else None,
        "mode": "full" if not degraded else "degraded",
    }


@router.get("/api/v1/debug/gpt-researcher")
async def debug_gpt_researcher():
    """Debug GPT Researcher configuration and Azure OpenAI connection. v2"""

    # Get GPT Researcher relevant env vars
    config_vars = {
        "SMART_LLM": os.getenv("SMART_LLM", "NOT SET"),
        "FAST_LLM": os.getenv("FAST_LLM", "NOT SET"),
        "EMBEDDING": os.getenv("EMBEDDING", "NOT SET"),
        "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "NOT SET"),
        "EMBEDDING_PROVIDER": os.getenv("EMBEDDING_PROVIDER", "NOT SET"),
        "OPENAI_API_VERSION": os.getenv("OPENAI_API_VERSION", "NOT SET"),
        "AZURE_OPENAI_API_VERSION": os.getenv("AZURE_OPENAI_API_VERSION", "NOT SET"),
        "SCRAPER": os.getenv("SCRAPER", "NOT SET"),
        "AZURE_OPENAI_ENDPOINT": (
            os.getenv("AZURE_OPENAI_ENDPOINT", "NOT SET")[:50] + "..."
            if os.getenv("AZURE_OPENAI_ENDPOINT")
            else "NOT SET"
        ),
        "AZURE_OPENAI_API_KEY": (
            "SET" if os.getenv("AZURE_OPENAI_API_KEY") else "NOT SET"
        ),
        "TAVILY_API_KEY": "SET" if os.getenv("TAVILY_API_KEY") else "NOT SET",
        "SERPER_API_KEY": "SET" if os.getenv("SERPER_API_KEY") else "NOT SET",
        "SEARXNG_BASE_URL": os.getenv("SEARXNG_BASE_URL", "NOT SET"),
        "SEARCH_PROVIDER": os.getenv("SEARCH_PROVIDER", "auto"),
    }

    # Test GPT Researcher config parsing
    gptr_config_status = "unknown"
    gptr_config_error = None
    parsed_config = {}

    try:
        from gpt_researcher.config import Config

        config = Config()
        parsed_config = {
            "fast_llm_provider": getattr(config, "fast_llm_provider", "N/A"),
            "fast_llm_model": getattr(config, "fast_llm_model", "N/A"),
            "smart_llm_provider": getattr(config, "smart_llm_provider", "N/A"),
            "smart_llm_model": getattr(config, "smart_llm_model", "N/A"),
            "embedding_provider": getattr(config, "embedding_provider", "N/A"),
            "embedding_model": getattr(config, "embedding_model", "N/A"),
        }
        gptr_config_status = "parsed"
    except Exception as e:
        gptr_config_status = "error"
        gptr_config_error = str(e)

    # Test LangChain Azure OpenAI connection (FAST + SMART deployments)
    langchain_tests: Dict[str, Any] = {}

    try:
        from langchain_openai import AzureChatOpenAI

        for label, deployment in [
            ("fast", parsed_config.get("fast_llm_model")),
            ("smart", parsed_config.get("smart_llm_model")),
        ]:
            env_key = "FAST_LLM" if label == "fast" else "SMART_LLM"
            deployment = deployment or os.getenv(env_key, "").split(":")[-1]
            try:
                llm = AzureChatOpenAI(
                    azure_deployment=deployment,
                    api_version=os.getenv("OPENAI_API_VERSION", "2024-05-01-preview"),
                    temperature=0,
                    max_tokens=10,
                )

                response = llm.invoke("Say 'hello' in one word")
                langchain_tests[label] = {
                    "status": "success",
                    "deployment": deployment,
                    "response": (
                        response.content
                        if hasattr(response, "content")
                        else str(response)
                    ),
                    "error": None,
                }
            except Exception as e:
                langchain_tests[label] = {
                    "status": "error",
                    "deployment": deployment,
                    "response": None,
                    "error": str(e),
                }
    except Exception as e:
        langchain_tests["import_error"] = {"status": "error", "error": str(e)}

    # Test GPT Researcher internal LLM utility (closest to agent selection path)
    gptr_llm_test: Dict[str, Any] = {
        "status": "unknown",
        "error": None,
        "response": None,
    }
    try:
        from gpt_researcher.config import Config
        from gpt_researcher.utils.llm import create_chat_completion

        cfg = Config()
        gptr_llm_test["provider"] = getattr(cfg, "smart_llm_provider", None)
        gptr_llm_test["model"] = getattr(cfg, "smart_llm_model", None)

        resp = await create_chat_completion(
            model=cfg.smart_llm_model,
            llm_provider=cfg.smart_llm_provider,
            llm_kwargs=cfg.llm_kwargs,
            messages=[{"role": "user", "content": "Reply with exactly: ok"}],
            temperature=0,
            max_tokens=8,
        )
        gptr_llm_test["status"] = "success"
        gptr_llm_test["response"] = resp
    except Exception as e:
        gptr_llm_test["status"] = "error"
        gptr_llm_test["error"] = str(e)

    # Search provider status
    from ..search_provider import get_provider_info

    search_status = get_provider_info()

    return {
        "env_vars": config_vars,
        "search_provider": search_status,
        "gptr_config": {
            "status": gptr_config_status,
            "error": gptr_config_error,
            "parsed": parsed_config,
        },
        "langchain_azure_test": langchain_tests,
        "gptr_llm_test": gptr_llm_test,
    }
