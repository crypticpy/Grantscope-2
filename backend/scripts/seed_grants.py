"""Seed the database with public health grants from Grants.gov.

Usage:
    cd backend
    python3 -m scripts.seed_grants [--max-cards 50] [--dry-run]

Fetches real grant opportunities from the Grants.gov public API using curl
(more reliable than Python HTTP clients due to TLS/SNI quirks), runs them
through AI triage and classification, and creates card records.
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app.database import async_session_factory
from app.deps import openai_client
from app.ai_service import AIService
from app.models.db.card import Card
from app.models.db.source import Source, DiscoveredSource
from app.models.db.card_extras import CardTimeline
from app.models.db.discovery import DiscoveryRun
from app.helpers.db_utils import vector_search_cards
from app.openai_provider import get_embedding_deployment, azure_openai_embedding_client
from app.discovery_service import convert_pillar_id, convert_goal_id, STAGE_NUMBER_TO_ID

from sqlalchemy import select, func, text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("seed_grants")

# Austin Public Health search topics
PUBLIC_HEALTH_TOPICS = [
    "public health grants",
    "community health center funding",
    "health equity federal grants",
    "maternal child health grants",
    "substance abuse prevention grants",
    "mental health services grants",
    "epidemiology surveillance grants",
    "CDC community health grants",
    "HRSA health center grants",
    "immunization public health grants",
    "chronic disease prevention grants",
    "environmental health grants",
    "HIV STD prevention grants",
    "emergency preparedness public health",
    "WIC nutrition program grants",
    "health disparities minority health",
]

GRANTS_GOV_API = "https://api.grants.gov/v1/api/search2"
OPP_URL_TEMPLATE = "https://www.grants.gov/search-results-detail/{id}"

# CFDA prefixes relevant to municipal government
RELEVANT_CFDA_PREFIXES = {
    "10",
    "11",
    "14",
    "15",
    "16",
    "17",
    "20",
    "66",
    "81",
    "84",
    "93",
    "97",
}

RELEVANCE_KEYWORDS = {
    "municipal",
    "city",
    "local government",
    "urban",
    "community",
    "public health",
    "transportation",
    "transit",
    "infrastructure",
    "affordable housing",
    "homelessness",
    "public safety",
    "emergency",
    "water",
    "broadband",
    "climate",
    "resilience",
    "sustainability",
    "workforce",
    "economic development",
    "equity",
    "health",
}


def fetch_grants_curl(keyword: str, rows: int = 25) -> list:
    """Fetch grants from Grants.gov using curl (reliable)."""
    payload = json.dumps(
        {
            "keyword": keyword,
            "sortBy": "openDate",
            "rows": rows,
            "offset": 0,
        }
    )
    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-X",
                "POST",
                GRANTS_GOV_API,
                "-H",
                "Content-Type: application/json",
                "-d",
                payload,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(result.stdout)
        return data.get("data", {}).get("oppHits", [])
    except Exception as e:
        logger.warning(f"curl fetch failed for '{keyword}': {e}")
        return []


def is_relevant(opp: dict) -> bool:
    """Check if an opportunity is relevant to city government."""
    cfda_list = opp.get("cfdaList", []) or []
    if isinstance(cfda_list, str):
        cfda_list = [c.strip() for c in cfda_list.split(",")]
    for cfda in cfda_list:
        prefix = str(cfda).split(".")[0] if "." in str(cfda) else str(cfda)[:2]
        if prefix in RELEVANT_CFDA_PREFIXES:
            return True

    text = f"{opp.get('title', '')} {opp.get('description', '')}".lower()
    return any(kw in text for kw in RELEVANCE_KEYWORDS)


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def build_content(opp: dict) -> str:
    """Build structured content for AI analysis."""
    funding_parts = []
    if opp.get("estimatedFunding"):
        try:
            funding_parts.append(
                f"Estimated Total Funding: ${int(opp['estimatedFunding']):,}"
            )
        except (ValueError, TypeError):
            pass
    if opp.get("awardFloor"):
        try:
            funding_parts.append(f"Award Floor: ${int(opp['awardFloor']):,}")
        except (ValueError, TypeError):
            pass
    if opp.get("awardCeiling"):
        try:
            funding_parts.append(f"Award Ceiling: ${int(opp['awardCeiling']):,}")
        except (ValueError, TypeError):
            pass

    open_date = parse_date(opp.get("openDate"))
    close_date = parse_date(opp.get("closeDate"))
    open_str = open_date.strftime("%B %d, %Y") if open_date else "Not specified"
    close_str = close_date.strftime("%B %d, %Y") if close_date else "Not specified"

    return f"""\
Title: {opp.get('title', 'Untitled')}

Agency: {opp.get('agency', opp.get('agencyName', 'Unknown'))}
Opportunity Number: {opp.get('number', opp.get('opportunityNumber', 'N/A'))}
CFDA Numbers: {opp.get('cfdaList', 'N/A')}

Open Date: {open_str}
Close Date: {close_str}

Funding Information:
{chr(10).join(funding_parts) if funding_parts else 'Not specified'}

Cost Sharing Required: {'Yes' if opp.get('costSharing') else 'No'}

Description:
{opp.get('description', 'No description available.')}"""


def make_slug(name: str) -> str:
    """Generate a URL-safe slug from a name."""
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:200]


async def get_embedding(text: str) -> Optional[list]:
    """Generate embedding for text using Azure OpenAI."""
    try:
        client = azure_openai_embedding_client or openai_client
        response = client.embeddings.create(
            input=text[:8000],
            model=get_embedding_deployment(),
        )
        return response.data[0].embedding
    except Exception as e:
        logger.warning(f"Embedding failed: {e}")
        return None


async def run_seed(max_cards: int, dry_run: bool) -> None:
    if async_session_factory is None:
        logger.error("DATABASE_URL not set.")
        sys.exit(1)

    ai = AIService(openai_client)

    # Step 1: Fetch grants from Grants.gov
    # Strategy: one broad keyword fetch (avoids rate limiting), then filter.
    # If a pre-fetched file exists at /tmp/grants_health.json, use it.
    import time

    cache_file = "/tmp/grants_health.json"
    all_hits = []

    if os.path.exists(cache_file):
        logger.info(f"Loading cached grants from {cache_file}")
        with open(cache_file) as f:
            data = json.load(f)
        all_hits = data.get("data", {}).get("oppHits", [])
    else:
        logger.info("Fetching grants from Grants.gov (broad keyword search)...")
        for keyword in ["health", "community", "public safety"]:
            hits = fetch_grants_curl(keyword, rows=200)
            all_hits.extend(hits)
            logger.info(f"  '{keyword}': {len(hits)} hits")
            time.sleep(5)  # Generous delay to avoid rate limits

    # Deduplicate and filter for relevance
    all_opps = {}
    for opp in all_hits:
        opp_id = str(opp.get("id", ""))
        if opp_id and opp_id not in all_opps and is_relevant(opp):
            all_opps[opp_id] = opp

    logger.info(f"Total unique relevant opportunities: {len(all_opps)}")

    if not all_opps:
        logger.error(
            "No opportunities fetched. Try: curl -s -X POST "
            "'https://api.grants.gov/v1/api/search2' "
            "-H 'Content-Type: application/json' "
            '-d \'{"keyword":"health","rows":200}\' '
            f"> {cache_file}"
        )
        return

    # Step 2: AI triage and card creation
    async with async_session_factory() as db:
        # Create a discovery run record
        run_id = str(uuid.uuid4())
        run = DiscoveryRun(
            id=run_id,
            status="running",
            triggered_by="manual",
            summary_report={"stage": "processing", "source": "seed_grants"},
        )
        db.add(run)
        await db.flush()

        # Pre-load existing grants_gov_ids for dedup
        existing_ids_result = await db.execute(
            select(Card.grants_gov_id).where(Card.grants_gov_id.isnot(None))
        )
        existing_gov_ids = {r[0] for r in existing_ids_result.all()}
        logger.info(f"Existing cards with grants_gov_id: {len(existing_gov_ids)}")

        created = 0
        skipped = 0
        triage_failed = 0

        for opp_id, opp in list(all_opps.items()):
            if created >= max_cards:
                break

            # Skip already-imported grants
            if opp_id in existing_gov_ids:
                skipped += 1
                continue

            title = opp.get("title", "Untitled")
            content = build_content(opp)
            url = OPP_URL_TEMPLATE.format(id=opp_id)

            # AI triage
            try:
                triage = await ai.triage_source(title, content)
                if not triage or not triage.is_relevant:
                    triage_failed += 1
                    continue
            except Exception as e:
                logger.warning(f"Triage failed for '{title[:50]}': {e}")
                triage_failed += 1
                continue

            # AI classification
            open_date = parse_date(opp.get("openDate"))
            published_str = open_date.strftime("%Y-%m-%d") if open_date else ""
            try:
                analysis = await ai.analyze_source(title, content, url, published_str)
                if not analysis:
                    logger.warning(f"Analysis returned None for '{title[:50]}'")
                    continue
            except Exception as e:
                logger.warning(f"Analysis failed for '{title[:50]}': {e}")
                continue

            # Check for duplicate by name similarity
            slug = make_slug(analysis.suggested_card_name or title)
            existing = await db.execute(select(Card).where(Card.slug == slug))
            if existing.scalar_one_or_none():
                slug = f"{slug}-{opp_id[:8]}"

            # Generate embedding
            embed_text = f"{analysis.suggested_card_name or title}. {analysis.summary or content[:500]}"
            embedding = await get_embedding(embed_text)

            # Parse grant-specific fields
            close_date = parse_date(opp.get("closeDate"))
            open_date = parse_date(opp.get("openDate"))
            agency = opp.get("agency", opp.get("agencyName", ""))
            cfda_list = opp.get("cfdaList", [])
            if isinstance(cfda_list, str):
                cfda_list = cfda_list
            elif isinstance(cfda_list, list):
                cfda_list = ", ".join(str(c) for c in cfda_list)
            else:
                cfda_list = ""

            funding_max = None
            funding_min = None
            try:
                if opp.get("awardCeiling"):
                    funding_max = int(opp["awardCeiling"])
                if opp.get("awardFloor"):
                    funding_min = int(opp["awardFloor"])
            except (ValueError, TypeError):
                pass

            # Create card (match discovery_service.py patterns)
            stage_id = STAGE_NUMBER_TO_ID.get(analysis.suggested_stage, "4_proof")
            pillar_id = (
                convert_pillar_id(analysis.pillars[0]) if analysis.pillars else None
            )
            goal_id = convert_goal_id(analysis.goals[0]) if analysis.goals else None
            now = datetime.now(timezone.utc)

            card = Card(
                id=str(uuid.uuid4()),
                name=analysis.suggested_card_name or title,
                slug=slug,
                summary=analysis.summary,
                description=content[:2000],
                pillar_id=pillar_id,
                goal_id=goal_id,
                stage_id=stage_id,
                horizon=analysis.horizon or "H1",
                # DB columns are NUMERIC(3,2) — max 9.99; raw AI values fit
                novelty_score=round(analysis.novelty, 2),
                maturity_score=round(analysis.credibility, 2),
                impact_score=round(analysis.impact, 2),
                relevance_score=round(analysis.relevance, 2),
                velocity_score=round(analysis.velocity, 2),
                risk_score=round(analysis.risk, 2),
                status="active",
                review_status="pending_review",
                ai_confidence=(
                    round(float(triage.confidence), 2)
                    if triage and hasattr(triage, "confidence")
                    else 0.8
                ),
                discovery_run_id=uuid.UUID(run_id),
                discovered_at=now,
                created_at=now,
                updated_at=now,
                # embedding stored via UPDATE after flush (pgvector needs raw SQL)
                # Grant-specific fields
                grant_type="federal",
                grantor=agency,
                deadline=close_date,
                cfda_number=cfda_list,
                grants_gov_id=opp_id,
                source_url=url,
                funding_amount_min=funding_min,
                funding_amount_max=funding_max,
            )

            if not dry_run:
                db.add(card)
                await db.flush()

                # Store embedding via raw SQL (pgvector needs ::vector cast)
                if embedding:
                    try:
                        vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
                        await db.execute(
                            text(
                                "UPDATE cards SET embedding = CAST(:vec AS vector) WHERE id = CAST(:cid AS uuid)"
                            ),
                            {"vec": vec_str, "cid": str(card.id)},
                        )
                    except Exception as emb_err:
                        logger.warning(f"Failed to store embedding: {emb_err}")

                # Add source record
                source = Source(
                    id=str(uuid.uuid4()),
                    card_id=card.id,
                    url=url,
                    title=title,
                    content=content[:5000],
                    source_type="grants_gov",
                    publisher=agency,
                    relevance_score=round(analysis.relevance, 2),
                    published_date=open_date,
                )
                db.add(source)

                # Add timeline event
                timeline = CardTimeline(
                    id=str(uuid.uuid4()),
                    card_id=card.id,
                    event_type="created",
                    title="Discovered from Grants.gov",
                    description=f"Imported from Grants.gov opportunity {opp.get('number', opp_id)}",
                )
                db.add(timeline)

            created += 1
            logger.info(
                f"[{created}/{max_cards}] Created: {card.name[:60]} "
                f"| Pillar: {card.pillar_id} | Deadline: {close_date}"
            )

        # Update discovery run
        run.status = "completed"
        run.summary_report = {
            "stage": "completed",
            "cards_created": created,
            "triage_filtered": triage_failed,
            "skipped": skipped,
            "total_fetched": len(all_opps),
        }

        if not dry_run:
            await db.commit()

        logger.info("=" * 60)
        logger.info("SEED COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Cards created:     {created}")
        logger.info(f"Triage filtered:   {triage_failed}")
        logger.info(f"Total fetched:     {len(all_opps)}")
        if dry_run:
            logger.info("DRY RUN — no changes persisted.")


def main():
    parser = argparse.ArgumentParser(
        description="Seed GrantScope with public health grants from Grants.gov"
    )
    parser.add_argument(
        "--max-cards",
        type=int,
        default=50,
        help="Maximum grant cards to create (default: 50)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and analyze grants but don't persist to database",
    )
    args = parser.parse_args()
    asyncio.run(run_seed(args.max_cards, args.dry_run))


if __name__ == "__main__":
    main()
