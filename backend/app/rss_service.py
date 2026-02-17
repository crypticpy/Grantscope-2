"""
RSS Feed Monitoring Service for GrantScope.

Manages RSS feed subscriptions, polls feeds on schedule, triages new articles
for relevance to municipal intelligence, and matches them to existing signal
cards or queues them for the signal agent.

Phase 3, Layer 2.1

Usage:
    from app.rss_service import RSSService

    service = RSSService(supabase_client, ai_service)
    stats = await service.check_feeds()
    process_stats = await service.process_new_items()
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from supabase import Client

from .ai_service import AIService
from .crawler import crawl_url
from .source_fetchers.rss_fetcher import fetch_single_feed

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SIMILARITY_MATCH_THRESHOLD = 0.85  # Strong match — attach source to card
SIMILARITY_WEAK_THRESHOLD = 0.75  # Weak match — still worth linking
MAX_ERROR_COUNT = 5  # Disable feed after this many consecutive errors


def _content_hash(title: str, url: str) -> str:
    """Compute a deterministic SHA-256 hash for dedup within a feed."""
    raw = f"{title.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class RSSService:
    """
    Core RSS monitoring service.

    Responsibilities:
      - Poll feeds on their configured schedule
      - Insert new feed items (articles) with dedup
      - Triage items for relevance via AIService
      - Match relevant items to existing cards via embedding similarity
      - Create source records for matched items
      - Expose CRUD operations for feed management
    """

    def __init__(self, supabase: Client, ai_service: AIService):
        self.supabase = supabase
        self.ai_service = ai_service

    # -----------------------------------------------------------------------
    # 1. check_feeds — poll feeds that are due
    # -----------------------------------------------------------------------

    async def check_feeds(self, max_feeds: int = 10) -> Dict[str, Any]:
        """
        Check feeds that are due for polling.

        Queries ``rss_feeds`` where ``status = 'active'`` and
        ``next_check_at <= now()``, then fetches each feed.

        Args:
            max_feeds: Maximum number of feeds to check in this batch.

        Returns:
            Dict with stats: feeds_checked, items_found, items_new, errors.
        """
        stats = {
            "feeds_checked": 0,
            "items_found": 0,
            "items_new": 0,
            "errors": 0,
        }

        try:
            result = (
                self.supabase.table("rss_feeds")
                .select("*")
                .eq("status", "active")
                .lte("next_check_at", _now_iso())
                .order("next_check_at")
                .limit(max_feeds)
                .execute()
            )
            feeds = result.data or []
        except Exception as e:
            logger.error(f"Failed to query due feeds: {e}")
            return stats

        if not feeds:
            logger.debug("No feeds due for checking")
            return stats

        logger.info(f"Checking {len(feeds)} due feeds")

        for feed in feeds:
            try:
                feed_stats = await self._check_one_feed(feed)
                stats["feeds_checked"] += 1
                stats["items_found"] += feed_stats["items_found"]
                stats["items_new"] += feed_stats["items_new"]
            except Exception as e:
                logger.error(f"Error checking feed {feed.get('name', '?')}: {e}")
                stats["errors"] += 1
                # Mark error on the feed record
                await self._record_feed_error(feed, str(e))

        logger.info(
            f"Feed check complete: {stats['feeds_checked']} feeds, "
            f"{stats['items_found']} items found, {stats['items_new']} new, "
            f"{stats['errors']} errors"
        )
        return stats

    # -----------------------------------------------------------------------
    # 2. _check_one_feed — fetch and store items from a single feed
    # -----------------------------------------------------------------------

    async def _check_one_feed(self, feed: dict) -> Dict[str, Any]:
        """
        Fetch a single feed and insert new items into ``rss_feed_items``.

        Uses ``fetch_single_feed()`` from the existing RSS fetcher module.
        Deduplicates via ``ON CONFLICT`` on ``(feed_id, url)`` unique index.

        Args:
            feed: Row dict from the ``rss_feeds`` table.

        Returns:
            Dict with items_found, items_new counts.
        """
        feed_id = feed["id"]
        feed_url = feed["url"]
        feed_name = feed.get("name", feed_url)

        logger.debug(f"Checking feed: {feed_name} ({feed_url})")

        result = await fetch_single_feed(feed_url)

        if not result.success:
            await self._record_feed_error(feed, result.error_message or "Unknown error")
            return {"items_found": 0, "items_new": 0}

        items_found = len(result.articles)
        items_new = 0

        for article in result.articles:
            try:
                content_hash = _content_hash(article.title, article.url)

                item_record = {
                    "feed_id": feed_id,
                    "url": article.url,
                    "title": (article.title or "Untitled")[:500],
                    "content": (article.content or "")[:10000],
                    "author": (article.author or "")[:200] if article.author else None,
                    "published_at": (
                        article.published_at.isoformat()
                        if article.published_at
                        else None
                    ),
                    "content_hash": content_hash,
                    "metadata": {
                        "tags": article.tags[:10] if article.tags else [],
                        "source_name": article.source_name,
                    },
                }

                # Upsert — the unique index on (feed_id, url) handles dedup
                insert_result = (
                    self.supabase.table("rss_feed_items")
                    .upsert(item_record, on_conflict="feed_id,url")
                    .execute()
                )

                if insert_result.data:
                    # Check if it was a new insert vs update.  New items have
                    # processed=False by default; updated items keep their state.
                    row = insert_result.data[0]
                    if row.get("processed") is False:
                        items_new += 1

            except Exception as e:
                logger.warning(
                    f"Failed to insert item '{article.title[:50]}' from {feed_name}: {e}"
                )

        # Update feed metadata
        now = _now_iso()
        interval_hours = feed.get("check_interval_hours", 6)
        next_check = (
            datetime.now(timezone.utc) + timedelta(hours=interval_hours)
        ).isoformat()

        update_data: Dict[str, Any] = {
            "last_checked_at": now,
            "next_check_at": next_check,
            "error_count": 0,
            "last_error": None,
            "updated_at": now,
            "articles_found_total": (feed.get("articles_found_total", 0) or 0)
            + items_found,
        }

        # Store feed-level metadata from the parsed feed
        if result.feed_title:
            update_data["feed_title"] = result.feed_title
        if result.feed_link:
            update_data["feed_link"] = result.feed_link

        try:
            self.supabase.table("rss_feeds").update(update_data).eq(
                "id", feed_id
            ).execute()
        except Exception as e:
            logger.warning(f"Failed to update feed metadata for {feed_name}: {e}")

        logger.info(f"Feed '{feed_name}': {items_found} items found, {items_new} new")
        return {"items_found": items_found, "items_new": items_new}

    # -----------------------------------------------------------------------
    # 3. process_new_items — triage and match unprocessed feed items
    # -----------------------------------------------------------------------

    async def process_new_items(self, batch_size: int = 20) -> Dict[str, Any]:
        """
        Fetch unprocessed feed items, triage for relevance, and match to
        existing signal cards.

        Pipeline per item:
          1. Crawl full article text via ``crawl_url()``
          2. Triage with ``ai_service.triage_source()``
          3. If relevant: generate embedding and match to existing cards
          4. If matched: create a source record, update item with card_id/source_id
          5. If not matched but relevant: mark ``triage_result='pending'``
          6. If irrelevant: mark ``triage_result='irrelevant'``
          7. Set ``processed=TRUE`` in all cases

        Args:
            batch_size: Max items to process in this call.

        Returns:
            Dict with items_processed, items_matched, items_pending, items_irrelevant.
        """
        stats = {
            "items_processed": 0,
            "items_matched": 0,
            "items_pending": 0,
            "items_irrelevant": 0,
        }

        try:
            result = (
                self.supabase.table("rss_feed_items")
                .select("*, rss_feeds(name, category, pillar_id)")
                .eq("processed", False)
                .order("published_at", desc=True)
                .limit(batch_size)
                .execute()
            )
            items = result.data or []
        except Exception as e:
            logger.error(f"Failed to fetch unprocessed items: {e}")
            return stats

        if not items:
            logger.debug("No unprocessed feed items")
            return stats

        logger.info(f"Processing {len(items)} unprocessed feed items")

        for item in items:
            try:
                await self._process_one_item(item, stats)
            except Exception as e:
                logger.error(
                    f"Error processing item '{item.get('title', '?')[:50]}': {e}"
                )
                # Still mark as processed to avoid infinite retry loops
                self._mark_processed(item["id"], triage_result="irrelevant")
                stats["items_processed"] += 1
                stats["items_irrelevant"] += 1

        logger.info(
            f"Item processing complete: {stats['items_processed']} processed, "
            f"{stats['items_matched']} matched, {stats['items_pending']} pending, "
            f"{stats['items_irrelevant']} irrelevant"
        )
        return stats

    async def _process_one_item(self, item: dict, stats: Dict[str, int]) -> None:
        """Process a single feed item through triage and card matching."""
        item_id = item["id"]
        feed_id = item["feed_id"]
        title = item.get("title", "Untitled")
        url = item.get("url", "")

        # Step 1: Crawl full content
        content = item.get("content", "") or ""
        if url:
            try:
                crawl_result = await crawl_url(url)
                if crawl_result.success and crawl_result.markdown:
                    content = crawl_result.markdown
            except Exception as e:
                logger.warning(f"Crawl failed for {url}: {e}")
                # Fall back to feed-provided content

        if not content and not title:
            self._mark_processed(item_id, triage_result="irrelevant")
            stats["items_processed"] += 1
            stats["items_irrelevant"] += 1
            return

        # Step 2: Triage for relevance
        triage = await self.ai_service.triage_source(title, content)

        if not triage.is_relevant:
            self._mark_processed(item_id, triage_result="irrelevant")
            stats["items_processed"] += 1
            stats["items_irrelevant"] += 1
            return

        # Step 3: Generate embedding for card matching
        embed_text = f"{title}\n\n{content[:6000]}"
        try:
            embedding = await self.ai_service.generate_embedding(embed_text)
        except Exception as e:
            logger.warning(f"Embedding generation failed for '{title[:50]}': {e}")
            # Mark as pending — signal agent can pick it up later
            self._mark_processed(item_id, triage_result="pending")
            stats["items_processed"] += 1
            stats["items_pending"] += 1
            return

        # Step 4: Match to existing cards via vector similarity
        matched_card_id = await self._find_matching_card(embedding)

        if matched_card_id:
            # Create a source record on the matched card
            source_id = await self._create_source_for_card(
                card_id=matched_card_id,
                title=title,
                url=url,
                content=content,
                triage=triage,
                feed_name=self._feed_name(item),
            )
            self._mark_processed(
                item_id,
                triage_result="matched",
                card_id=matched_card_id,
                source_id=source_id,
            )
            # Increment matched total on the feed
            self._increment_feed_matched(feed_id)
            stats["items_processed"] += 1
            stats["items_matched"] += 1
        else:
            # Relevant but no card match — mark as pending for signal agent
            self._mark_processed(item_id, triage_result="pending")
            stats["items_processed"] += 1
            stats["items_pending"] += 1

    async def _find_matching_card(self, embedding: List[float]) -> Optional[str]:
        """
        Find a matching card using vector similarity search.

        Tries the database ``find_similar_cards`` RPC first, falling back to
        Python-based cosine similarity if the RPC is unavailable.

        Returns:
            Card UUID string if a strong match is found, else None.
        """
        # Try database RPC first
        try:
            match_result = self.supabase.rpc(
                "find_similar_cards",
                {
                    "query_embedding": embedding,
                    "match_threshold": SIMILARITY_WEAK_THRESHOLD,
                    "match_count": 3,
                },
            ).execute()

            if match_result.data:
                top = match_result.data[0]
                similarity = top.get("similarity", 0)
                if similarity >= SIMILARITY_MATCH_THRESHOLD:
                    logger.info(
                        f"RSS item matched card '{top.get('name', '?')}' "
                        f"(similarity={similarity:.3f})"
                    )
                    return top["id"]
                elif similarity >= SIMILARITY_WEAK_THRESHOLD:
                    # Weak match — still link, better to enrich than miss
                    logger.info(
                        f"RSS item weakly matched card '{top.get('name', '?')}' "
                        f"(similarity={similarity:.3f}) — linking"
                    )
                    return top["id"]
        except Exception as e:
            logger.warning(f"find_similar_cards RPC failed: {e}")
            # Fall back to Python-based search
            return await self._python_card_search(embedding)

        return None

    async def _python_card_search(self, embedding: List[float]) -> Optional[str]:
        """
        Fallback: fetch card embeddings and compute cosine similarity in Python.
        """
        from .discovery_service import cosine_similarity

        try:
            cards_result = (
                self.supabase.table("cards")
                .select("id, name, embedding")
                .eq("status", "approved")
                .limit(200)
                .execute()
            )
            cards = cards_result.data or []
        except Exception as e:
            logger.error(f"Failed to fetch cards for Python fallback: {e}")
            return None

        best_id: Optional[str] = None
        best_sim = 0.0

        for card in cards:
            card_emb = card.get("embedding")
            if not card_emb:
                continue
            sim = cosine_similarity(embedding, card_emb)
            if sim > best_sim:
                best_sim = sim
                best_id = card["id"]

        if best_id and best_sim >= SIMILARITY_WEAK_THRESHOLD:
            logger.info(
                f"Python fallback matched card {best_id} (similarity={best_sim:.3f})"
            )
            return best_id

        return None

    async def _create_source_for_card(
        self,
        card_id: str,
        title: str,
        url: str,
        content: str,
        triage: Any,
        feed_name: str,
    ) -> Optional[str]:
        """Create a source record linked to a card for a matched feed item."""
        try:
            from app.source_quality import extract_domain

            source_record = {
                "card_id": card_id,
                "url": url,
                "title": (title or "Untitled")[:500],
                "publication": feed_name[:200] if feed_name else None,
                "full_text": content[:10000] if content else None,
                "ai_summary": triage.reason if triage else None,
                "relevance_to_card": (triage.confidence if triage else 0.5),
                "api_source": "rss_monitor",
                "domain": extract_domain(url),
                "ingested_at": _now_iso(),
            }

            result = self.supabase.table("sources").insert(source_record).execute()

            if result.data:
                source_id = result.data[0]["id"]
                logger.info(
                    f"Created source {source_id} on card {card_id} "
                    f"from RSS: {title[:50]}"
                )

                # Compute quality score (non-blocking)
                try:
                    from app.source_quality import compute_and_store_quality_score

                    compute_and_store_quality_score(
                        self.supabase, source_id, triage=triage
                    )
                except Exception as e:
                    logger.warning(
                        f"Quality score computation failed for source {source_id}: {e}"
                    )

                return source_id

        except Exception as e:
            if "duplicate" not in str(e).lower():
                logger.error(f"Failed to create source for card {card_id}: {e}")
        return None

    # -----------------------------------------------------------------------
    # 4. get_feed_stats
    # -----------------------------------------------------------------------

    async def get_feed_stats(self) -> List[dict]:
        """
        Return all feeds with stats.

        Each entry includes: name, url, status, last_checked_at, error_count,
        articles_found_total, articles_matched_total, and the count of items
        created in the last 7 days.
        """
        try:
            feeds_result = (
                self.supabase.table("rss_feeds").select("*").order("name").execute()
            )
            feeds = feeds_result.data or []
        except Exception as e:
            logger.error(f"Failed to fetch feed stats: {e}")
            return []

        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        enriched: List[dict] = []
        for feed in feeds:
            # Count recent items for this feed
            recent_count = 0
            try:
                count_result = (
                    self.supabase.table("rss_feed_items")
                    .select("id", count="exact")
                    .eq("feed_id", feed["id"])
                    .gte("created_at", seven_days_ago)
                    .execute()
                )
                recent_count = count_result.count or 0
            except Exception:
                pass

            enriched.append(
                {
                    "id": feed["id"],
                    "name": feed["name"],
                    "url": feed["url"],
                    "category": feed.get("category"),
                    "pillar_id": feed.get("pillar_id"),
                    "status": feed.get("status"),
                    "check_interval_hours": feed.get("check_interval_hours"),
                    "last_checked_at": feed.get("last_checked_at"),
                    "error_count": feed.get("error_count", 0),
                    "last_error": feed.get("last_error"),
                    "feed_title": feed.get("feed_title"),
                    "feed_link": feed.get("feed_link"),
                    "articles_found_total": feed.get("articles_found_total", 0),
                    "articles_matched_total": feed.get("articles_matched_total", 0),
                    "recent_items_7d": recent_count,
                    "created_at": feed.get("created_at"),
                    "updated_at": feed.get("updated_at"),
                }
            )

        return enriched

    # -----------------------------------------------------------------------
    # 5. add_feed
    # -----------------------------------------------------------------------

    async def add_feed(
        self,
        url: str,
        name: str,
        category: str = "general",
        pillar_id: Optional[str] = None,
        check_interval_hours: int = 6,
    ) -> dict:
        """
        Add a new RSS feed subscription and perform an initial check.

        Args:
            url: Feed URL.
            name: Human-readable feed name.
            category: Feed category (gov_tech, municipal, academic, news, etc.).
            pillar_id: Optional strategic pillar to lock this feed to.
            check_interval_hours: How often to check (1–168 hours).

        Returns:
            The inserted feed record dict.
        """
        feed_record = {
            "url": url,
            "name": name,
            "category": category,
            "pillar_id": pillar_id,
            "check_interval_hours": max(1, min(168, check_interval_hours)),
            "next_check_at": _now_iso(),
        }

        try:
            result = self.supabase.table("rss_feeds").insert(feed_record).execute()
            if not result.data:
                raise ValueError("Insert returned no data")
            feed = result.data[0]
        except Exception as e:
            logger.error(f"Failed to add feed '{name}' ({url}): {e}")
            raise

        # Perform initial check immediately
        try:
            await self._check_one_feed(feed)
        except Exception as e:
            logger.warning(f"Initial check failed for new feed '{name}': {e}")

        # Re-fetch to return the updated record (with feed_title, etc.)
        try:
            refreshed = (
                self.supabase.table("rss_feeds")
                .select("*")
                .eq("id", feed["id"])
                .single()
                .execute()
            )
            return refreshed.data or feed
        except Exception:
            return feed

    # -----------------------------------------------------------------------
    # 6. update_feed
    # -----------------------------------------------------------------------

    async def update_feed(self, feed_id: str, **kwargs) -> dict:
        """
        Update feed fields.

        Allowed fields: name, category, pillar_id, check_interval_hours, status.

        Returns:
            The updated feed record.
        """
        allowed_fields = {
            "name",
            "category",
            "pillar_id",
            "check_interval_hours",
            "status",
        }
        update_data: Dict[str, Any] = {
            k: v for k, v in kwargs.items() if k in allowed_fields
        }

        if not update_data:
            raise ValueError(f"No valid fields to update. Allowed: {allowed_fields}")

        # Clamp interval
        if "check_interval_hours" in update_data:
            update_data["check_interval_hours"] = max(
                1, min(168, update_data["check_interval_hours"])
            )

        update_data["updated_at"] = _now_iso()

        try:
            result = (
                self.supabase.table("rss_feeds")
                .update(update_data)
                .eq("id", feed_id)
                .execute()
            )
            if result.data:
                return result.data[0]
            raise ValueError(f"Feed {feed_id} not found")
        except Exception as e:
            logger.error(f"Failed to update feed {feed_id}: {e}")
            raise

    # -----------------------------------------------------------------------
    # 7. delete_feed
    # -----------------------------------------------------------------------

    async def delete_feed(self, feed_id: str) -> bool:
        """
        Delete a feed and cascade-delete its items.

        Returns:
            True if deleted successfully.
        """
        try:
            self.supabase.table("rss_feeds").delete().eq("id", feed_id).execute()
            logger.info(f"Deleted feed {feed_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete feed {feed_id}: {e}")
            return False

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    async def _record_feed_error(self, feed: dict, error_msg: str) -> None:
        """Increment error count and optionally disable the feed."""
        feed_id = feed["id"]
        error_count = (feed.get("error_count", 0) or 0) + 1
        new_status = (
            "error" if error_count > MAX_ERROR_COUNT else feed.get("status", "active")
        )

        # Even on error, schedule the next check so it can recover
        interval_hours = feed.get("check_interval_hours", 6)
        next_check = (
            datetime.now(timezone.utc) + timedelta(hours=interval_hours)
        ).isoformat()

        try:
            self.supabase.table("rss_feeds").update(
                {
                    "error_count": error_count,
                    "last_error": error_msg[:1000],
                    "status": new_status,
                    "last_checked_at": _now_iso(),
                    "next_check_at": next_check,
                    "updated_at": _now_iso(),
                }
            ).eq("id", feed_id).execute()
        except Exception as e:
            logger.warning(f"Failed to record error for feed {feed_id}: {e}")

        if error_count > MAX_ERROR_COUNT:
            logger.warning(
                f"Feed '{feed.get('name', feed_id)}' disabled after "
                f"{error_count} consecutive errors"
            )

    def _mark_processed(
        self,
        item_id: str,
        triage_result: str,
        card_id: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> None:
        """Mark a feed item as processed with its triage outcome."""
        update_data: Dict[str, Any] = {
            "processed": True,
            "triage_result": triage_result,
        }
        if card_id:
            update_data["card_id"] = card_id
        if source_id:
            update_data["source_id"] = source_id

        try:
            self.supabase.table("rss_feed_items").update(update_data).eq(
                "id", item_id
            ).execute()
        except Exception as e:
            logger.warning(f"Failed to mark item {item_id} as processed: {e}")

    def _increment_feed_matched(self, feed_id: str) -> None:
        """Increment the articles_matched_total counter on a feed."""
        try:
            # Read current value then increment (no RPC needed for simple +1)
            feed_result = (
                self.supabase.table("rss_feeds")
                .select("articles_matched_total")
                .eq("id", feed_id)
                .single()
                .execute()
            )
            current = (
                feed_result.data.get("articles_matched_total", 0) or 0
                if feed_result.data
                else 0
            )
            self.supabase.table("rss_feeds").update(
                {
                    "articles_matched_total": current + 1,
                    "updated_at": _now_iso(),
                }
            ).eq("id", feed_id).execute()
        except Exception as e:
            logger.warning(f"Failed to increment matched count for feed {feed_id}: {e}")

    @staticmethod
    def _feed_name(item: dict) -> str:
        """Extract the feed name from a joined item row."""
        feed_info = item.get("rss_feeds")
        if isinstance(feed_info, dict):
            return feed_info.get("name", "RSS Feed")
        return "RSS Feed"
