"""Classification validation router."""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import supabase, get_current_user, _safe_error
from app.models.classification_models import (
    VALID_PILLAR_CODES,
    ValidationSubmission,
    ValidationSubmissionResponse,
)
from app.models.processing_metrics import ClassificationMetrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["classification"])


@router.post(
    "/validation/submit",
    response_model=ValidationSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_validation_label(
    submission: ValidationSubmission, current_user: dict = Depends(get_current_user)
):
    """
    Submit a ground truth classification label for a card.

    Allows reviewers to provide the correct pillar classification for a card,
    enabling accuracy tracking and model improvement. The submission is compared
    against the card's predicted pillar to determine classification correctness.

    Args:
        submission: Validation submission with card_id, ground_truth_pillar, and reviewer_id

    Returns:
        The created validation record with correctness determination

    Raises:
        HTTPException 404: Card not found
        HTTPException 400: Duplicate validation by same reviewer for same card
    """
    now = datetime.now().isoformat()

    # Verify the card exists and get its predicted pillar
    card_check = (
        supabase.table("cards")
        .select("id, pillar_id")
        .eq("id", submission.card_id)
        .execute()
    )

    if not card_check.data:
        raise HTTPException(status_code=404, detail="Card not found")

    card = card_check.data[0]
    predicted_pillar = card.get("pillar_id")

    # Check for duplicate validation by same reviewer
    existing_check = (
        supabase.table("classification_validations")
        .select("id")
        .eq("card_id", submission.card_id)
        .eq("reviewer_id", submission.reviewer_id)
        .execute()
    )

    if existing_check.data:
        raise HTTPException(
            status_code=400,
            detail="Validation already exists for this card by this reviewer",
        )

    # Determine if classification is correct
    is_correct = (
        predicted_pillar == submission.ground_truth_pillar if predicted_pillar else None
    )

    # Create validation record
    validation_record = {
        "card_id": submission.card_id,
        "ground_truth_pillar": submission.ground_truth_pillar,
        "predicted_pillar": predicted_pillar,
        "is_correct": is_correct,
        "reviewer_id": submission.reviewer_id,
        "notes": submission.notes,
        "created_at": now,
        "created_by": current_user["id"],
    }

    response = (
        supabase.table("classification_validations").insert(validation_record).execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=500, detail="Failed to create validation record"
        )

    logger.info(
        f"Validation submitted for card {submission.card_id}: "
        f"ground_truth={submission.ground_truth_pillar}, "
        f"predicted={predicted_pillar}, is_correct={is_correct}"
    )

    return ValidationSubmissionResponse(**response.data[0])


@router.get("/validation/stats")
async def get_validation_stats(current_user: dict = Depends(get_current_user)):
    """
    Get classification validation statistics.

    Returns aggregate statistics on classification accuracy based on
    submitted ground truth labels.

    Returns:
        Dictionary with total validations, correct count, accuracy percentage
    """
    # Get all validations with correctness determined
    validations_response = (
        supabase.table("classification_validations")
        .select("is_correct")
        .not_.is_("is_correct", "null")
        .execute()
    )

    if not validations_response.data:
        return {
            "total_validations": 0,
            "correct_count": 0,
            "incorrect_count": 0,
            "accuracy_percentage": None,
            "target_accuracy": 85.0,
        }

    total = len(validations_response.data)
    correct = sum(1 for v in validations_response.data if v["is_correct"])
    incorrect = total - correct
    accuracy = (correct / total * 100) if total > 0 else 0

    return {
        "total_validations": total,
        "correct_count": correct,
        "incorrect_count": incorrect,
        "accuracy_percentage": round(accuracy, 2),
        "target_accuracy": 85.0,
        "meets_target": accuracy >= 85.0,
    }


@router.get("/validation/pending")
async def get_cards_pending_validation(
    current_user: dict = Depends(get_current_user), limit: int = 20, offset: int = 0
):
    """
    Get cards that need validation (have predictions but no ground truth labels).

    Returns active cards with pillar_id set but no corresponding validation record,
    prioritized by creation date (newest first).

    Args:
        limit: Maximum number of cards to return (default: 20)
        offset: Number of cards to skip for pagination

    Returns:
        List of cards needing validation
    """
    # Get cards with predictions
    cards_response = (
        supabase.table("cards")
        .select("id, name, summary, pillar_id, created_at")
        .eq("status", "active")
        .not_.is_("pillar_id", "null")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    if not cards_response.data:
        return []

    # Get card IDs that already have validations
    card_ids = [c["id"] for c in cards_response.data]
    validated_response = (
        supabase.table("classification_validations")
        .select("card_id")
        .in_("card_id", card_ids)
        .execute()
    )

    validated_ids = (
        {v["card_id"] for v in validated_response.data}
        if validated_response.data
        else set()
    )

    # Filter to only cards without validations
    pending_cards = [c for c in cards_response.data if c["id"] not in validated_ids]

    return pending_cards


@router.get("/validation/accuracy", response_model=ClassificationMetrics)
async def get_classification_accuracy(
    current_user: dict = Depends(get_current_user), days: Optional[int] = None
):
    """
    Compute classification accuracy from validation data.

    Returns detailed accuracy metrics based on submitted ground truth labels,
    including overall accuracy, per-pillar breakdown, and target achievement status.

    The target accuracy is 85% for production-quality classification.

    Args:
        days: Optional number of days to look back (default: all time)

    Returns:
        ClassificationMetrics with:
        - total_validations: Total number of validations with correctness determined
        - correct_count: Number of correct classifications
        - accuracy_percentage: Accuracy as percentage (0-100)
        - target_accuracy: Target accuracy threshold (85%)
        - meets_target: Boolean indicating if target is met

    Note:
        Only validations where is_correct is not null are included in accuracy
        computation. Cards without predicted pillars are excluded.
    """
    # Build query for validations with correctness determined
    query = (
        supabase.table("classification_validations")
        .select("is_correct, ground_truth_pillar, predicted_pillar, created_at")
        .not_.is_("is_correct", "null")
    )

    # Apply date filter if specified
    if days is not None and days > 0:
        period_start = (datetime.now() - timedelta(days=days)).isoformat()
        query = query.gte("created_at", period_start)

    validations_response = query.execute()

    if not validations_response.data:
        # No validations yet - return empty metrics
        return ClassificationMetrics(
            total_validations=0,
            correct_count=0,
            accuracy_percentage=None,
            target_accuracy=85.0,
            meets_target=False,
        )

    # Compute accuracy metrics
    total_validations = len(validations_response.data)
    correct_count = sum(1 for v in validations_response.data if v.get("is_correct"))
    accuracy_percentage = (
        (correct_count / total_validations * 100) if total_validations > 0 else None
    )

    logger.info(
        f"Classification accuracy computed: {correct_count}/{total_validations} "
        f"({accuracy_percentage:.2f}% accuracy)"
        if accuracy_percentage
        else f"Classification accuracy: No validations available"
    )

    return ClassificationMetrics(
        total_validations=total_validations,
        correct_count=correct_count,
        accuracy_percentage=(
            round(accuracy_percentage, 2) if accuracy_percentage else None
        ),
        target_accuracy=85.0,
        meets_target=accuracy_percentage >= 85.0 if accuracy_percentage else False,
    )


@router.get("/validation/accuracy/by-pillar")
async def get_accuracy_by_pillar(
    current_user: dict = Depends(get_current_user), days: Optional[int] = None
):
    """
    Get classification accuracy broken down by pillar.

    Provides per-pillar accuracy metrics to identify which strategic pillars
    have higher or lower classification accuracy, enabling targeted improvement.

    Args:
        days: Optional number of days to look back (default: all time)

    Returns:
        Dictionary with:
        - overall: Overall ClassificationMetrics
        - by_pillar: Dict mapping pillar codes to accuracy metrics
        - confusion_summary: Summary of common misclassifications
    """
    # Build query for validations with correctness determined
    query = (
        supabase.table("classification_validations")
        .select("is_correct, ground_truth_pillar, predicted_pillar, created_at")
        .not_.is_("is_correct", "null")
    )

    # Apply date filter if specified
    if days is not None and days > 0:
        period_start = (datetime.now() - timedelta(days=days)).isoformat()
        query = query.gte("created_at", period_start)

    validations_response = query.execute()

    if not validations_response.data:
        return {
            "overall": {
                "total_validations": 0,
                "correct_count": 0,
                "accuracy_percentage": None,
                "target_accuracy": 85.0,
                "meets_target": False,
            },
            "by_pillar": {},
            "confusion_summary": [],
        }

    # Compute overall metrics
    total_validations = len(validations_response.data)
    correct_count = sum(1 for v in validations_response.data if v.get("is_correct"))
    accuracy_percentage = (
        (correct_count / total_validations * 100) if total_validations > 0 else None
    )

    # Compute per-pillar metrics
    pillar_stats = defaultdict(lambda: {"total": 0, "correct": 0})
    confusion_pairs = defaultdict(int)

    for v in validations_response.data:
        ground_truth = v.get("ground_truth_pillar")
        predicted = v.get("predicted_pillar")
        is_correct = v.get("is_correct")

        if ground_truth:
            pillar_stats[ground_truth]["total"] += 1
            if is_correct:
                pillar_stats[ground_truth]["correct"] += 1
            elif predicted:
                # Track confusion pairs
                confusion_pairs[(predicted, ground_truth)] += 1

    # Format per-pillar results
    by_pillar = {}
    for pillar, stats in pillar_stats.items():
        pillar_accuracy = (
            (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else None
        )
        by_pillar[pillar] = {
            "total_validations": stats["total"],
            "correct_count": stats["correct"],
            "accuracy_percentage": (
                round(pillar_accuracy, 2) if pillar_accuracy else None
            ),
            "meets_target": pillar_accuracy >= 85.0 if pillar_accuracy else False,
        }

    # Format confusion summary (top misclassifications)
    confusion_summary = [
        {"predicted": pred, "actual": actual, "count": count}
        for (pred, actual), count in sorted(
            confusion_pairs.items(), key=lambda x: x[1], reverse=True
        )[
            :10
        ]  # Top 10 confusion pairs
    ]

    return {
        "overall": {
            "total_validations": total_validations,
            "correct_count": correct_count,
            "accuracy_percentage": (
                round(accuracy_percentage, 2) if accuracy_percentage else None
            ),
            "target_accuracy": 85.0,
            "meets_target": (
                accuracy_percentage >= 85.0 if accuracy_percentage else False
            ),
        },
        "by_pillar": by_pillar,
        "confusion_summary": confusion_summary,
    }
