"""
Backfill embeddings for all active cards and run connection discovery.

This script:
1. Fetches all active cards that have NULL embeddings
2. Generates embeddings using OpenAI (text-embedding-ada-002)
3. Updates each card's embedding column in the database
4. Runs connection discovery to populate card_relationships

Supports both standard OpenAI (OPENAI_API_KEY) and Azure OpenAI
(AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_KEY).

Usage:
    cd backend
    source venv/bin/activate
    python -m backfill_embeddings
"""

import os
import sys
import asyncio
import logging
import time
from typing import List

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    logger.critical("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ---------------------------------------------------------------------------
# OpenAI client — supports both standard and Azure
# ---------------------------------------------------------------------------
from openai import AsyncOpenAI, AsyncAzureOpenAI

AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_KEY = os.getenv("AZURE_OPENAI_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

EMBEDDING_MODEL = "text-embedding-ada-002"

if AZURE_ENDPOINT and AZURE_KEY:
    logger.info(f"Using Azure OpenAI at {AZURE_ENDPOINT}")
    embedding_client = AsyncAzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        api_key=AZURE_KEY,
        api_version=os.getenv("AZURE_OPENAI_EMBEDDING_API_VERSION", "2023-05-15"),
    )
elif OPENAI_KEY:
    logger.info("Using standard OpenAI API")
    embedding_client = AsyncOpenAI(api_key=OPENAI_KEY)
else:
    logger.critical(
        "No OpenAI credentials found. Set OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_KEY"
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BATCH_SIZE = 10
BATCH_DELAY_SECS = 1.5


# ---------------------------------------------------------------------------
# Embedding generation (standalone, no AIService dependency)
# ---------------------------------------------------------------------------
async def generate_embedding(text: str) -> List[float]:
    """Generate 1536-dim embedding for text."""
    truncated = text[:8000] if len(text) > 8000 else text
    response = await embedding_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=truncated,
    )
    return response.data[0].embedding


def compose_embedding_text(card: dict) -> str:
    """Build the text string to embed from a card's fields."""
    name = card.get("name") or ""
    summary = card.get("summary") or ""
    description = card.get("description") or ""
    return f"{name} {summary} {description}".strip()


async def process_card(card: dict) -> bool:
    """Generate an embedding for a single card and store it. Returns True on success."""
    card_id = card["id"]
    text = compose_embedding_text(card)

    if len(text) < 10:
        logger.warning(f"  Card {card_id} has insufficient text, skipping")
        return False

    try:
        embedding = await generate_embedding(text)
        supabase.table("cards").update({"embedding": embedding}).eq(
            "id", card_id
        ).execute()
        return True
    except Exception as exc:
        logger.error(f"  Failed to embed card {card_id}: {exc}")
        return False


# ---------------------------------------------------------------------------
# Connection discovery (uses ConnectionService which needs AIService)
# ---------------------------------------------------------------------------
async def run_connection_discovery(card_count: int) -> None:
    """Run connection discovery after embeddings are backfilled."""
    logger.info("Initializing ConnectionService for connection discovery...")

    # ConnectionService needs AIService for LLM classification
    # AIService needs an async OpenAI client
    # ConnectionService._classify_connection uses self.ai_service.client (sync)
    # which calls chat.completions.create — needs a sync client
    try:
        # ConnectionService imports ai_service which imports openai_provider
        # at module level. openai_provider raises ValueError if Azure vars missing.
        # We must stub out openai_provider BEFORE importing connection_service.
        if not AZURE_ENDPOINT:
            import types

            # Create a stub module to prevent the real openai_provider from loading
            stub = types.ModuleType("app.openai_provider")
            stub.get_chat_mini_deployment = lambda: "gpt-4o-mini"
            stub.get_chat_deployment = lambda: "gpt-4o"
            stub.get_embedding_deployment = lambda: "text-embedding-ada-002"
            stub.get_embedding_api_version = lambda: "2023-05-15"
            stub.get_chat_api_version = lambda: "2024-12-01-preview"
            # Provide dummy client objects that ai_service module-level expects
            from openai import OpenAI, AsyncOpenAI

            stub.azure_openai_client = OpenAI(api_key=OPENAI_KEY)
            stub.azure_openai_async_client = AsyncOpenAI(api_key=OPENAI_KEY)
            stub.azure_openai_embedding_client = OpenAI(api_key=OPENAI_KEY)
            stub.azure_openai_async_embedding_client = AsyncOpenAI(api_key=OPENAI_KEY)

            import sys as _sys

            _sys.modules["app.openai_provider"] = stub
            logger.info("Stubbed app.openai_provider for standard OpenAI")

        # Now safe to import connection_service and its dependencies
        if AZURE_ENDPOINT and AZURE_KEY:
            from openai import AzureOpenAI

            sync_client = AzureOpenAI(
                azure_endpoint=AZURE_ENDPOINT,
                api_key=AZURE_KEY,
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
            )
        else:
            from openai import OpenAI

            sync_client = OpenAI(api_key=OPENAI_KEY)

        # Create a minimal AIService-like object that has .client attribute
        # (ConnectionService._classify_connection calls self.ai_service.client)
        class MinimalAIService:
            def __init__(self, client):
                self.client = client

        ai_svc = MinimalAIService(sync_client)

        from app.connection_service import ConnectionService

        conn_service = ConnectionService(supabase=supabase, ai_service=ai_svc)

        summary = await conn_service.refresh_all_connections(batch_size=card_count)

        logger.info("=" * 60)
        logger.info("Connection Discovery Summary")
        for key, value in summary.items():
            logger.info(f"  {key}: {value}")
        logger.info("=" * 60)

    except Exception as exc:
        logger.error(f"Connection discovery failed: {exc}", exc_info=True)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
async def main() -> None:
    start_time = time.time()

    # Step 1: Fetch all active cards without embeddings
    logger.info("Fetching active cards with NULL embeddings...")

    response = (
        supabase.table("cards")
        .select("id, name, summary, description")
        .eq("status", "active")
        .is_("embedding", "null")
        .execute()
    )

    cards = response.data
    total = len(cards)

    if total == 0:
        logger.info("All active cards already have embeddings. Nothing to do.")
        return

    logger.info(f"Found {total} cards needing embeddings.")

    # Step 2: Generate embeddings in batches
    success_count = 0
    failure_count = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total)
        batch = cards[batch_start:batch_end]
        batch_num = (batch_start // BATCH_SIZE) + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        logger.info(
            f"Batch {batch_num}/{total_batches} "
            f"(cards {batch_start + 1}-{batch_end} of {total})..."
        )

        results = await asyncio.gather(
            *[process_card(card) for card in batch],
            return_exceptions=True,
        )

        for i, result in enumerate(results):
            card = batch[i]
            if isinstance(result, Exception):
                logger.error(f"  {card.get('name', '?')[:50]}: exception - {result}")
                failure_count += 1
            elif result:
                logger.info(f"  {card.get('name', '?')[:50]}: embedded")
                success_count += 1
            else:
                failure_count += 1

        if batch_end < total:
            await asyncio.sleep(BATCH_DELAY_SECS)

    elapsed = time.time() - start_time

    logger.info("=" * 60)
    logger.info("Embedding Backfill Summary")
    logger.info(f"  Total cards:  {total}")
    logger.info(f"  Succeeded:    {success_count}")
    logger.info(f"  Failed:       {failure_count}")
    logger.info(f"  Elapsed:      {elapsed:.1f}s")
    logger.info("=" * 60)

    if success_count == 0:
        logger.warning("No embeddings generated. Skipping connection discovery.")
        return

    # Step 3: Run connection discovery
    await run_connection_discovery(success_count)

    total_elapsed = time.time() - start_time
    logger.info(f"Total elapsed: {total_elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
