"""Workstream utility functions extracted from main.py.

Functions for filtering cards against workstream criteria, building scan
configurations, and auto-queuing workstream scans.
"""

import logging
from typing import Any, Dict, List

from supabase import Client

logger = logging.getLogger(__name__)


def _filter_cards_for_workstream(
    workstream: dict,
    cards: List[dict],
) -> List[dict]:
    """Apply pillar/goal/horizon/stage/keyword filters for a workstream."""
    filtered = cards

    ws_pillar_ids = workstream.get("pillar_ids") or []
    if ws_pillar_ids:
        filtered = [c for c in filtered if c.get("pillar_id") in ws_pillar_ids]

    ws_goal_ids = workstream.get("goal_ids") or []
    if ws_goal_ids:
        filtered = [c for c in filtered if c.get("goal_id") in ws_goal_ids]

    ws_horizon = workstream.get("horizon")
    if ws_horizon and ws_horizon != "ALL":
        filtered = [c for c in filtered if c.get("horizon") == ws_horizon]

    ws_stage_ids = workstream.get("stage_ids") or []
    if ws_stage_ids:

        def _stage_num(card_stage_id: str) -> str:
            return (
                card_stage_id.split("_", 1)[0]
                if "_" in card_stage_id
                else card_stage_id
            )

        filtered = [
            c for c in filtered if _stage_num((c.get("stage_id") or "")) in ws_stage_ids
        ]

    ws_keywords = [k.lower() for k in (workstream.get("keywords") or [])]
    if ws_keywords:

        def _card_text(card: dict) -> str:
            return " ".join(
                [
                    (card.get("name") or "").lower(),
                    (card.get("summary") or "").lower(),
                    (card.get("description") or "").lower(),
                ]
            )

        filtered = [
            c for c in filtered if any(kw in _card_text(c) for kw in ws_keywords)
        ]

    return filtered


def _build_workstream_scan_config(ws: dict, triggered_by: str) -> dict:
    """Build a standardized workstream scan config dict."""
    return {
        "workstream_id": ws["id"],
        "user_id": ws.get("user_id"),
        "keywords": ws.get("keywords") or [],
        "pillar_ids": ws.get("pillar_ids") or [],
        "horizon": ws.get("horizon") or "ALL",
        "triggered_by": triggered_by,
    }


def _auto_queue_workstream_scan(
    supabase_client: Client,
    workstream_id: str,
    user_id: str,
    config: dict,
) -> bool:
    """Queue a workstream scan directly into the workstream_scans table.

    This bypasses the per-user rate limit because it is triggered by the
    system (post-creation or auto-scan scheduler), not by a manual user action.

    Args:
        supabase_client: Supabase client instance
        workstream_id: UUID of the workstream
        user_id: UUID of the workstream owner
        config: Scan configuration dict (keywords, pillar_ids, horizon, etc.)

    Returns:
        True if the scan was successfully queued, False otherwise
    """
    try:
        scan_record = {
            "workstream_id": workstream_id,
            "user_id": user_id,
            "status": "queued",
            "config": config,
        }
        result = supabase_client.table("workstream_scans").insert(scan_record).execute()
        if result.data:
            scan_id = result.data[0]["id"]
            logger.info(
                f"Auto-queued workstream scan {scan_id} for workstream {workstream_id} "
                f"(triggered_by: {config.get('triggered_by', 'unknown')})"
            )
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to auto-queue scan for workstream {workstream_id}: {e}")
        return False
