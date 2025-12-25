#!/usr/bin/env python3
"""
Stage History Backfill Script

This script backfills stage history data from the card_timeline table,
populating the enhanced stage tracking columns (old_stage_id, new_stage_id,
old_horizon, new_horizon, trigger, reason) from existing timeline events.

The script identifies stage transitions from:
1. Events with event_type='stage_changed'
2. Events with previous_value/new_value containing stage information
3. Events that indicate stage or horizon changes in event_description

Usage:
    # Dry run - show what would be backfilled
    python -m scripts.backfill_stage_history --dry-run

    # Execute backfill
    python -m scripts.backfill_stage_history

    # Backfill with verbose output
    python -m scripts.backfill_stage_history --verbose

    # Limit backfill to specific card
    python -m scripts.backfill_stage_history --card-id <uuid>

Environment Variables:
    SUPABASE_URL: Supabase project URL
    SUPABASE_SERVICE_KEY: Supabase service role key (or SUPABASE_ANON_KEY)
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from supabase import create_client, Client
except ImportError:
    print("Error: supabase package not installed. Run: pip install supabase")
    sys.exit(1)


# Horizon mapping from stage ID
# Stages 1-2: H3 (Emerging/Future)
# Stages 3-5: H2 (Mid-term)
# Stages 6-8: H1 (Near-term/Current)
def stage_to_horizon(stage_id: Optional[int]) -> Optional[str]:
    """Convert stage ID (1-8) to horizon (H1, H2, H3)."""
    if stage_id is None:
        return None
    if 1 <= stage_id <= 2:
        return "H3"
    elif 3 <= stage_id <= 5:
        return "H2"
    elif 6 <= stage_id <= 8:
        return "H1"
    return None


@dataclass
class StageTransition:
    """Represents a stage transition extracted from timeline data."""
    timeline_id: str
    card_id: str
    created_at: str
    old_stage_id: Optional[int] = None
    new_stage_id: Optional[int] = None
    old_horizon: Optional[str] = None
    new_horizon: Optional[str] = None
    trigger: Optional[str] = None
    reason: Optional[str] = None
    needs_update: bool = False
    source: str = "unknown"  # Where the data was extracted from


@dataclass
class BackfillReport:
    """Report summarizing the backfill operation."""
    total_timeline_events: int = 0
    stage_events_found: int = 0
    events_needing_update: int = 0
    events_updated: int = 0
    events_skipped: int = 0
    events_failed: int = 0
    errors: List[str] = field(default_factory=list)
    transitions: List[StageTransition] = field(default_factory=list)


class StageHistoryBackfill:
    """Handles backfilling stage history data from card_timeline."""

    def __init__(self, verbose: bool = False):
        """Initialize with Supabase connection."""
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError(
                "Missing SUPABASE_URL or SUPABASE_SERVICE_KEY environment variables"
            )

        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.verbose = verbose

    def log(self, message: str):
        """Print message if verbose mode enabled."""
        if self.verbose:
            print(f"  {message}")

    def fetch_timeline_events(
        self,
        card_id: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Fetch timeline events that may contain stage transition data.

        Args:
            card_id: Optional filter to specific card
            limit: Maximum records to fetch per batch

        Returns:
            List of timeline event records
        """
        query = self.supabase.table("card_timeline").select(
            "id, card_id, event_type, event_description, "
            "previous_value, new_value, old_stage_id, new_stage_id, "
            "old_horizon, new_horizon, trigger, reason, created_at"
        )

        if card_id:
            query = query.eq("card_id", card_id)

        # Order by created_at to process chronologically
        query = query.order("created_at", desc=False).limit(limit)

        response = query.execute()
        return response.data or []

    def extract_stage_from_value(
        self,
        value: Any
    ) -> Tuple[Optional[int], Optional[str]]:
        """
        Extract stage_id and horizon from a timeline value.

        Args:
            value: The previous_value or new_value (could be JSON, dict, or string)

        Returns:
            Tuple of (stage_id, horizon)
        """
        if value is None:
            return None, None

        # If it's a string, try to parse as JSON
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # Try to extract stage from string like "stage: 3" or "Stage 3"
                match = re.search(r'stage[:\s]*(\d+)', value, re.IGNORECASE)
                if match:
                    stage_id = int(match.group(1))
                    if 1 <= stage_id <= 8:
                        return stage_id, stage_to_horizon(stage_id)

                # Try to extract horizon from string like "horizon: H2" or "H2"
                match = re.search(r'(H[123])', value, re.IGNORECASE)
                if match:
                    horizon = match.group(1).upper()
                    return None, horizon

                return None, None

        if isinstance(value, dict):
            stage_id = None
            horizon = None

            # Look for stage_id in various formats
            for key in ["stage_id", "stage", "maturity_stage", "stageId"]:
                if key in value:
                    try:
                        stage_id = int(value[key])
                        if 1 <= stage_id <= 8:
                            break
                        else:
                            stage_id = None
                    except (ValueError, TypeError):
                        pass

            # Look for horizon in various formats
            for key in ["horizon", "planning_horizon"]:
                if key in value and value[key] in ("H1", "H2", "H3"):
                    horizon = value[key]
                    break

            # If we have stage but no horizon, derive it
            if stage_id and not horizon:
                horizon = stage_to_horizon(stage_id)

            return stage_id, horizon

        return None, None

    def extract_trigger_from_event(
        self,
        event: Dict[str, Any]
    ) -> Optional[str]:
        """
        Extract trigger type from timeline event.

        Args:
            event: Timeline event record

        Returns:
            Trigger string or None
        """
        event_type = event.get("event_type", "").lower()
        description = (event.get("event_description") or "").lower()

        # Map event types to triggers
        if "auto" in event_type or "calculated" in event_type:
            return "auto-calculated"
        if "manual" in event_type or "user" in event_type:
            return "manual"
        if "source" in event_type or "update" in event_type:
            return "source-update"
        if "system" in event_type:
            return "system"

        # Check description for clues
        if "auto" in description or "calculated" in description:
            return "auto-calculated"
        if "manual" in description or "user" in description:
            return "manual"

        # Check if triggered by user
        if event.get("triggered_by_user_id"):
            return "manual"

        # Check if triggered by source
        if event.get("triggered_by_source_id"):
            return "source-update"

        return None

    def is_stage_change_event(self, event: Dict[str, Any]) -> bool:
        """
        Determine if a timeline event represents a stage change.

        Args:
            event: Timeline event record

        Returns:
            True if this event is a stage change
        """
        event_type = event.get("event_type", "").lower()
        description = (event.get("event_description") or "").lower()

        # Explicit stage change event
        if event_type == "stage_changed":
            return True

        # Check for stage-related keywords in event type
        stage_keywords = ["stage", "maturity", "horizon", "progression"]
        if any(kw in event_type for kw in stage_keywords):
            return True

        # Check description for stage change indicators
        if any(kw in description for kw in stage_keywords):
            return True

        # Check if previous_value or new_value contain stage information
        prev_stage, prev_horizon = self.extract_stage_from_value(
            event.get("previous_value")
        )
        new_stage, new_horizon = self.extract_stage_from_value(
            event.get("new_value")
        )

        # If we can extract stage info, it's likely a stage change
        if (prev_stage or new_stage) and prev_stage != new_stage:
            return True
        if (prev_horizon or new_horizon) and prev_horizon != new_horizon:
            return True

        return False

    def extract_transition(
        self,
        event: Dict[str, Any]
    ) -> Optional[StageTransition]:
        """
        Extract stage transition data from a timeline event.

        Args:
            event: Timeline event record

        Returns:
            StageTransition object or None if not a valid transition
        """
        # Check if already has populated stage columns
        has_existing_data = (
            event.get("new_stage_id") is not None or
            event.get("new_horizon") is not None
        )

        # Extract from previous_value and new_value
        old_stage, old_horizon = self.extract_stage_from_value(
            event.get("previous_value")
        )
        new_stage, new_horizon = self.extract_stage_from_value(
            event.get("new_value")
        )

        # Use existing data if present
        if event.get("old_stage_id") is not None:
            old_stage = event["old_stage_id"]
        if event.get("new_stage_id") is not None:
            new_stage = event["new_stage_id"]
        if event.get("old_horizon"):
            old_horizon = event["old_horizon"]
        if event.get("new_horizon"):
            new_horizon = event["new_horizon"]

        # Derive horizons from stages if not present
        if old_stage and not old_horizon:
            old_horizon = stage_to_horizon(old_stage)
        if new_stage and not new_horizon:
            new_horizon = stage_to_horizon(new_stage)

        # Skip if no meaningful stage data
        if new_stage is None and new_horizon is None:
            return None

        # Extract trigger
        trigger = event.get("trigger") or self.extract_trigger_from_event(event)

        # Use event_description as reason if no reason set
        reason = event.get("reason") or event.get("event_description")

        transition = StageTransition(
            timeline_id=event["id"],
            card_id=event["card_id"],
            created_at=event.get("created_at", ""),
            old_stage_id=old_stage,
            new_stage_id=new_stage,
            old_horizon=old_horizon,
            new_horizon=new_horizon,
            trigger=trigger,
            reason=reason,
            needs_update=not has_existing_data,
            source="extracted" if not has_existing_data else "existing"
        )

        return transition

    def update_timeline_record(
        self,
        transition: StageTransition
    ) -> bool:
        """
        Update a timeline record with stage transition data.

        Args:
            transition: StageTransition with data to update

        Returns:
            True if update succeeded
        """
        update_data = {}

        if transition.old_stage_id is not None:
            update_data["old_stage_id"] = transition.old_stage_id
        if transition.new_stage_id is not None:
            update_data["new_stage_id"] = transition.new_stage_id
        if transition.old_horizon:
            update_data["old_horizon"] = transition.old_horizon
        if transition.new_horizon:
            update_data["new_horizon"] = transition.new_horizon
        if transition.trigger:
            update_data["trigger"] = transition.trigger
        if transition.reason:
            # Truncate reason to reasonable length
            update_data["reason"] = transition.reason[:1000] if transition.reason else None

        if not update_data:
            return False

        try:
            self.supabase.table("card_timeline").update(
                update_data
            ).eq("id", transition.timeline_id).execute()
            return True
        except Exception as e:
            self.log(f"Failed to update {transition.timeline_id}: {e}")
            return False

    def run_backfill(
        self,
        dry_run: bool = True,
        card_id: Optional[str] = None
    ) -> BackfillReport:
        """
        Run the backfill operation.

        Args:
            dry_run: If True, don't actually update records
            card_id: Optional filter to specific card

        Returns:
            BackfillReport with operation results
        """
        report = BackfillReport()

        print(f"\n{'=' * 60}")
        print("STAGE HISTORY BACKFILL")
        print(f"{'=' * 60}")
        print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
        if card_id:
            print(f"Card Filter: {card_id}")
        print()

        # Fetch timeline events
        print("Fetching timeline events...")
        events = self.fetch_timeline_events(card_id=card_id)
        report.total_timeline_events = len(events)
        print(f"Found {report.total_timeline_events} timeline events")

        # Process events
        print("\nAnalyzing events for stage transitions...")
        for event in events:
            if not self.is_stage_change_event(event):
                continue

            report.stage_events_found += 1
            transition = self.extract_transition(event)

            if transition is None:
                self.log(f"Skipping event {event['id']} - no stage data extracted")
                report.events_skipped += 1
                continue

            report.transitions.append(transition)

            if transition.needs_update:
                report.events_needing_update += 1

                if not dry_run:
                    if self.update_timeline_record(transition):
                        report.events_updated += 1
                        self.log(
                            f"Updated {transition.timeline_id}: "
                            f"stage {transition.old_stage_id} -> {transition.new_stage_id}"
                        )
                    else:
                        report.events_failed += 1
                        report.errors.append(
                            f"Failed to update {transition.timeline_id}"
                        )

        return report

    def print_report(self, report: BackfillReport, dry_run: bool = True):
        """Print a formatted report of the backfill operation."""
        print(f"\n{'-' * 60}")
        print("BACKFILL SUMMARY")
        print(f"{'-' * 60}")
        print(f"Total timeline events scanned: {report.total_timeline_events}")
        print(f"Stage change events found: {report.stage_events_found}")
        print(f"Events needing update: {report.events_needing_update}")

        if not dry_run:
            print(f"Events updated: {report.events_updated}")
            print(f"Events failed: {report.events_failed}")
        else:
            print("\n[DRY RUN - No changes made]")

        print(f"Events skipped (no data): {report.events_skipped}")

        # Show sample transitions
        if report.transitions:
            print(f"\n{'-' * 60}")
            print("STAGE TRANSITIONS FOUND")
            print(f"{'-' * 60}")
            print(f"{'Card ID':<38} {'Old Stage':<12} {'New Stage':<12} {'Source':<10}")
            print("-" * 72)

            for t in report.transitions[:20]:  # Show first 20
                old_stage = f"{t.old_stage_id or '?'} ({t.old_horizon or '?'})"
                new_stage = f"{t.new_stage_id or '?'} ({t.new_horizon or '?'})"
                print(f"{t.card_id[:36]:<38} {old_stage:<12} {new_stage:<12} {t.source:<10}")

            if len(report.transitions) > 20:
                print(f"... and {len(report.transitions) - 20} more transitions")

        if report.errors:
            print(f"\n{'-' * 60}")
            print("ERRORS")
            print(f"{'-' * 60}")
            for error in report.errors[:10]:
                print(f"  - {error}")

        print(f"\n{'=' * 60}")

        return report.events_failed == 0


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Backfill stage history data from card_timeline"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be backfilled without making changes"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show verbose output during processing"
    )
    parser.add_argument(
        "--card-id", "-c",
        type=str,
        help="Filter to specific card ID"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    try:
        backfill = StageHistoryBackfill(verbose=args.verbose)
        report = backfill.run_backfill(
            dry_run=args.dry_run,
            card_id=args.card_id
        )

        if args.json:
            result = {
                "total_events": report.total_timeline_events,
                "stage_events": report.stage_events_found,
                "needs_update": report.events_needing_update,
                "updated": report.events_updated,
                "skipped": report.events_skipped,
                "failed": report.events_failed,
                "dry_run": args.dry_run,
                "errors": report.errors,
                "transitions": [
                    {
                        "timeline_id": t.timeline_id,
                        "card_id": t.card_id,
                        "old_stage_id": t.old_stage_id,
                        "new_stage_id": t.new_stage_id,
                        "old_horizon": t.old_horizon,
                        "new_horizon": t.new_horizon,
                        "trigger": t.trigger,
                        "needs_update": t.needs_update
                    }
                    for t in report.transitions
                ]
            }
            print(json.dumps(result, indent=2))
        else:
            success = backfill.print_report(report, dry_run=args.dry_run)
            sys.exit(0 if success else 1)

    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
