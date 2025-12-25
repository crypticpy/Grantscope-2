#!/usr/bin/env python3
"""
Score History Backfill Script

This script populates the card_score_history table with initial snapshots
for existing cards that don't yet have historical data. This enables
trend visualization and comparison features from the start.

Usage:
    # Dry run - show what would be backfilled
    python -m scripts.backfill_score_history --dry-run

    # Execute backfill with default batch size
    python -m scripts.backfill_score_history

    # Execute with custom batch size
    python -m scripts.backfill_score_history --batch-size 50

    # Limit to specific number of cards (useful for testing)
    python -m scripts.backfill_score_history --limit 10

    # Show verbose output
    python -m scripts.backfill_score_history --verbose

Environment Variables:
    SUPABASE_URL: Supabase project URL
    SUPABASE_SERVICE_KEY: Supabase service role key (required for backfill)
"""

import argparse
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv


# Score columns that exist in both cards and card_score_history tables
SCORE_COLUMNS = [
    "maturity_score",
    "velocity_score",
    "novelty_score",
    "impact_score",
    "relevance_score",
    "risk_score",
    "opportunity_score",
]


class ScoreHistoryBackfill:
    """Handles score history backfill operations."""

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        verbose: bool = False,
    ):
        """
        Initialize the backfill handler.

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase service role key
            verbose: Enable verbose output
        """
        self.verbose = verbose
        self._supabase = None

        # Load environment variables if not provided
        load_dotenv()
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        self.supabase_key = supabase_key or os.getenv("SUPABASE_SERVICE_KEY")

        if not self.supabase_url or not self.supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables are required"
            )

    @property
    def supabase(self):
        """Lazy initialization of Supabase client."""
        if self._supabase is None:
            from supabase import create_client
            self._supabase = create_client(self.supabase_url, self.supabase_key)
        return self._supabase

    def _log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(f"  {message}")

    def get_cards_needing_backfill(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch cards that have scores but no history records.

        Args:
            limit: Optional limit on number of cards to fetch

        Returns:
            List of card dictionaries with score data
        """
        # Select cards with at least one non-null score
        select_columns = ["id", "name", "slug", "created_at", "updated_at"] + SCORE_COLUMNS

        query = self.supabase.table("cards").select(",".join(select_columns))

        # Filter to active cards only
        query = query.eq("status", "active")

        # Order by created_at for consistent processing
        query = query.order("created_at", desc=False)

        if limit:
            query = query.limit(limit)

        result = query.execute()
        cards = result.data or []

        # Filter to cards that have at least one non-null score
        cards_with_scores = [
            card for card in cards
            if any(card.get(col) is not None for col in SCORE_COLUMNS)
        ]

        return cards_with_scores

    def get_cards_with_existing_history(self) -> set:
        """
        Get set of card IDs that already have history records.

        Returns:
            Set of card UUIDs with existing history
        """
        result = self.supabase.table("card_score_history") \
            .select("card_id") \
            .execute()

        return {record["card_id"] for record in (result.data or [])}

    def filter_cards_without_history(
        self,
        cards: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Filter cards to only those without existing history.

        Args:
            cards: List of card dictionaries

        Returns:
            Filtered list of cards needing backfill
        """
        existing_ids = self.get_cards_with_existing_history()
        self._log(f"Found {len(existing_ids)} cards with existing history")

        return [card for card in cards if card["id"] not in existing_ids]

    def prepare_history_record(self, card: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare a history record from a card's current scores.

        Uses the card's created_at or updated_at as the recorded_at timestamp
        to represent the initial state.

        Args:
            card: Card dictionary with scores

        Returns:
            History record dictionary ready for insertion
        """
        # Use updated_at if available, otherwise created_at, otherwise now
        recorded_at = card.get("updated_at") or card.get("created_at") or datetime.now().isoformat()

        record = {
            "card_id": card["id"],
            "recorded_at": recorded_at,
        }

        # Copy all score columns
        for col in SCORE_COLUMNS:
            record[col] = card.get(col)

        return record

    def insert_history_batch(
        self,
        records: List[Dict[str, Any]],
    ) -> Tuple[int, int]:
        """
        Insert a batch of history records.

        Args:
            records: List of history records to insert

        Returns:
            Tuple of (successful count, failed count)
        """
        if not records:
            return 0, 0

        try:
            result = self.supabase.table("card_score_history") \
                .insert(records) \
                .execute()

            inserted = len(result.data) if result.data else 0
            return inserted, len(records) - inserted
        except Exception as e:
            print(f"Error inserting batch: {e}")
            return 0, len(records)

    def run_backfill(
        self,
        dry_run: bool = False,
        batch_size: int = 100,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute the backfill operation.

        Args:
            dry_run: If True, only report what would be done
            batch_size: Number of records to insert per batch
            limit: Optional limit on cards to process

        Returns:
            Summary dictionary with statistics
        """
        print("\n" + "=" * 60)
        print("Score History Backfill")
        print("=" * 60)

        if dry_run:
            print("MODE: Dry Run (no changes will be made)")
        else:
            print("MODE: Execute Backfill")

        print("-" * 60)

        # Step 1: Fetch cards with scores
        print("\n[1/4] Fetching cards with scores...")
        all_cards = self.get_cards_needing_backfill(limit=limit)
        print(f"      Found {len(all_cards)} cards with score data")

        if not all_cards:
            print("\n✅ No cards found with score data. Nothing to backfill.")
            return {
                "total_cards": 0,
                "cards_needing_backfill": 0,
                "records_inserted": 0,
                "errors": 0,
                "dry_run": dry_run,
            }

        # Step 2: Filter to cards without history
        print("\n[2/4] Checking for existing history records...")
        cards_to_backfill = self.filter_cards_without_history(all_cards)
        print(f"      {len(cards_to_backfill)} cards need backfill")

        if not cards_to_backfill:
            print("\n✅ All cards already have history records. Nothing to backfill.")
            return {
                "total_cards": len(all_cards),
                "cards_needing_backfill": 0,
                "records_inserted": 0,
                "errors": 0,
                "dry_run": dry_run,
            }

        # Step 3: Prepare records
        print("\n[3/4] Preparing history records...")
        records = [self.prepare_history_record(card) for card in cards_to_backfill]

        # Show sample records
        print(f"      Prepared {len(records)} records")
        if self.verbose and records:
            print("\n      Sample record:")
            sample = records[0]
            for key, value in sample.items():
                print(f"        {key}: {value}")

        # Dry run stops here
        if dry_run:
            print("\n" + "=" * 60)
            print("DRY RUN SUMMARY")
            print("=" * 60)
            print(f"\n  Total cards with scores: {len(all_cards)}")
            print(f"  Cards needing backfill: {len(cards_to_backfill)}")
            print(f"  Records to insert: {len(records)}")

            # Show cards that would be backfilled
            print(f"\n  Cards to backfill:")
            for i, card in enumerate(cards_to_backfill[:10]):
                scores_summary = ", ".join(
                    f"{col.replace('_score', '')}={card.get(col)}"
                    for col in SCORE_COLUMNS
                    if card.get(col) is not None
                )
                print(f"    {i+1}. {card.get('name', 'Unknown')} [{scores_summary}]")

            if len(cards_to_backfill) > 10:
                print(f"    ... and {len(cards_to_backfill) - 10} more")

            print("\n✅ Dry run complete. Run without --dry-run to execute.")
            return {
                "total_cards": len(all_cards),
                "cards_needing_backfill": len(cards_to_backfill),
                "records_to_insert": len(records),
                "records_inserted": 0,
                "errors": 0,
                "dry_run": True,
            }

        # Step 4: Insert records in batches
        print("\n[4/4] Inserting history records...")
        total_inserted = 0
        total_errors = 0

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(records) + batch_size - 1) // batch_size

            self._log(f"Processing batch {batch_num}/{total_batches} ({len(batch)} records)")

            inserted, errors = self.insert_history_batch(batch)
            total_inserted += inserted
            total_errors += errors

            if errors > 0:
                print(f"      ⚠️  Batch {batch_num}: {errors} errors")

        # Summary
        print("\n" + "=" * 60)
        print("BACKFILL SUMMARY")
        print("=" * 60)
        print(f"\n  Total cards with scores: {len(all_cards)}")
        print(f"  Cards processed: {len(cards_to_backfill)}")
        print(f"  Records inserted: {total_inserted}")
        print(f"  Errors: {total_errors}")

        if total_errors == 0:
            print("\n✅ Backfill completed successfully!")
        else:
            print(f"\n⚠️  Backfill completed with {total_errors} errors.")

        return {
            "total_cards": len(all_cards),
            "cards_needing_backfill": len(cards_to_backfill),
            "records_inserted": total_inserted,
            "errors": total_errors,
            "dry_run": False,
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill score history for existing cards",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of records to insert per batch (default: 100)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of cards to process (useful for testing)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--supabase-url",
        type=str,
        default=os.getenv("SUPABASE_URL"),
        help="Supabase project URL",
    )
    parser.add_argument(
        "--supabase-key",
        type=str,
        default=os.getenv("SUPABASE_SERVICE_KEY"),
        help="Supabase service role key",
    )

    args = parser.parse_args()

    try:
        backfill = ScoreHistoryBackfill(
            supabase_url=args.supabase_url,
            supabase_key=args.supabase_key,
            verbose=args.verbose,
        )

        result = backfill.run_backfill(
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            limit=args.limit,
        )

        # Exit with error code if there were errors
        if result.get("errors", 0) > 0:
            sys.exit(1)

    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}")
        print("\nMake sure to set environment variables:")
        print("  export SUPABASE_URL=your-project-url")
        print("  export SUPABASE_SERVICE_KEY=your-service-key")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
