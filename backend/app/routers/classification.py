"""Classification validation router."""

import logging
import uuid
from collections import defaultdict
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user_hardcoded, _safe_error
from app.models.classification_models import (
    VALID_PILLAR_CODES,
    ValidationSubmission,
    ValidationSubmissionResponse,
)
from app.models.processing_metrics import ClassificationMetrics
from app.models.db.card import Card
from app.models.db.analytics import ClassificationValidation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["classification"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(obj, skip_cols=None) -> dict:
    skip = skip_cols or set()
    result = {}
    for col in obj.__table__.columns:
        if col.name in skip:
            continue
        value = getattr(obj, col.key, None)
        if isinstance(value, uuid.UUID):
            result[col.name] = str(value)
        elif isinstance(value, (datetime, date)):
            result[col.name] = value.isoformat()
        elif isinstance(value, Decimal):
            result[col.name] = float(value)
        else:
            result[col.name] = value
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/validation/submit",
    response_model=ValidationSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_validation_label(
    submission: ValidationSubmission,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
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
    try:
        # Verify the card exists and get its predicted pillar
        card_stmt = select(Card.id, Card.pillar_id).where(Card.id == submission.card_id)
        card_result = await db.execute(card_stmt)
        card_row = card_result.one_or_none()

        if not card_row:
            raise HTTPException(status_code=404, detail="Card not found")

        predicted_pillar = card_row.pillar_id

        # Check for duplicate validation by same reviewer
        existing_stmt = (
            select(ClassificationValidation.id)
            .where(ClassificationValidation.card_id == submission.card_id)
            .where(ClassificationValidation.reviewer_id == submission.reviewer_id)
        )
        existing_result = await db.execute(existing_stmt)
        if existing_result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=400,
                detail="Validation already exists for this card by this reviewer",
            )

        # Guard: reject validation for unclassified cards
        if not predicted_pillar:
            raise HTTPException(
                status_code=400,
                detail="Card has no AI classification yet; cannot validate.",
            )

        # Create validation record
        validation = ClassificationValidation(
            card_id=submission.card_id,
            ground_truth_pillar=submission.ground_truth_pillar,
            predicted_pillar=predicted_pillar,
            is_correct=(predicted_pillar == submission.ground_truth_pillar),
            reviewer_id=submission.reviewer_id,
            notes=submission.notes,
        )
        db.add(validation)
        await db.flush()
        await db.refresh(validation)

        logger.info(
            f"Validation submitted for card {submission.card_id}: "
            f"ground_truth={submission.ground_truth_pillar}, "
            f"predicted={predicted_pillar}, is_correct={validation.is_correct}"
        )

        return ValidationSubmissionResponse(**_row_to_dict(validation))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit validation: {e}")
        raise HTTPException(
            status_code=500, detail=_safe_error("submit validation", e)
        ) from e


@router.get("/validation/stats")
async def get_validation_stats(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Get classification validation statistics.

    Returns aggregate statistics on classification accuracy based on
    submitted ground truth labels.

    Returns:
        Dictionary with total validations, correct count, accuracy percentage
    """
    try:
        # Get all validations with correctness determined
        stmt = select(ClassificationValidation.is_correct).where(
            ClassificationValidation.is_correct.isnot(None)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        if not rows:
            return {
                "total_validations": 0,
                "correct_count": 0,
                "incorrect_count": 0,
                "accuracy_percentage": None,
                "target_accuracy": 85.0,
            }

        total = len(rows)
        correct = sum(1 for v in rows if v)
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

    except Exception as e:
        logger.error(f"Failed to get validation stats: {e}")
        raise HTTPException(
            status_code=500, detail=_safe_error("get validation stats", e)
        ) from e


@router.get("/validation/pending")
async def get_cards_pending_validation(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
    limit: int = 20,
    offset: int = 0,
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
    try:
        # Get cards with predictions
        cards_stmt = (
            select(Card)
            .where(Card.status == "active")
            .where(Card.pillar_id.isnot(None))
            .order_by(Card.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        cards_result = await db.execute(cards_stmt)
        card_rows = cards_result.scalars().all()

        if not card_rows:
            return []

        # Get card IDs that already have validations
        card_ids = [row.id for row in card_rows]
        validated_stmt = select(ClassificationValidation.card_id).where(
            ClassificationValidation.card_id.in_(card_ids)
        )
        validated_result = await db.execute(validated_stmt)
        validated_ids = {row for row in validated_result.scalars().all()}

        # Return cards without validations, selecting only the fields the
        # original endpoint returned
        pending = []
        for c in card_rows:
            if c.id not in validated_ids:
                pending.append(
                    {
                        "id": str(c.id),
                        "name": c.name,
                        "summary": c.summary,
                        "pillar_id": c.pillar_id,
                        "created_at": (
                            c.created_at.isoformat() if c.created_at else None
                        ),
                    }
                )

        return pending

    except Exception as e:
        logger.error(f"Failed to get pending validations: {e}")
        raise HTTPException(
            status_code=500, detail=_safe_error("get pending validations", e)
        ) from e


@router.get("/validation/accuracy", response_model=ClassificationMetrics)
async def get_classification_accuracy(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
    days: Optional[int] = None,
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
    try:
        # Build query for validations with correctness determined
        stmt = select(ClassificationValidation).where(
            ClassificationValidation.is_correct.isnot(None)
        )

        # Apply date filter if specified
        if days is not None and days > 0:
            period_start = datetime.now(timezone.utc) - timedelta(days=days)
            stmt = stmt.where(ClassificationValidation.created_at >= period_start)

        result = await db.execute(stmt)
        rows = result.scalars().all()

        if not rows:
            # No validations yet - return empty metrics
            return ClassificationMetrics(
                total_validations=0,
                correct_count=0,
                accuracy_percentage=None,
                target_accuracy=85.0,
                meets_target=False,
            )

        # Compute accuracy metrics
        total_validations = len(rows)
        correct_count = sum(1 for v in rows if v.is_correct)
        accuracy_percentage = (
            (correct_count / total_validations * 100) if total_validations > 0 else None
        )

        logger.info(
            f"Classification accuracy computed: {correct_count}/{total_validations} ({accuracy_percentage:.2f}% accuracy)"
            if accuracy_percentage
            else "Classification accuracy: No validations available"
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

    except Exception as e:
        logger.error(f"Failed to compute classification accuracy: {e}")
        raise HTTPException(
            status_code=500, detail=_safe_error("classification accuracy", e)
        ) from e


@router.get("/validation/accuracy/by-pillar")
async def get_accuracy_by_pillar(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
    days: Optional[int] = None,
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
    try:
        # Build query for validations with correctness determined
        stmt = select(ClassificationValidation).where(
            ClassificationValidation.is_correct.isnot(None)
        )

        # Apply date filter if specified
        if days is not None and days > 0:
            period_start = datetime.now(timezone.utc) - timedelta(days=days)
            stmt = stmt.where(ClassificationValidation.created_at >= period_start)

        result = await db.execute(stmt)
        rows = result.scalars().all()

        if not rows:
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
        total_validations = len(rows)
        correct_count = sum(1 for v in rows if v.is_correct)
        accuracy_percentage = (
            (correct_count / total_validations * 100) if total_validations > 0 else None
        )

        # Compute per-pillar metrics
        pillar_stats = defaultdict(lambda: {"total": 0, "correct": 0})
        confusion_pairs = defaultdict(int)

        for v in rows:
            ground_truth = v.ground_truth_pillar
            predicted = v.predicted_pillar
            is_correct = v.is_correct

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
                (stats["correct"] / stats["total"] * 100)
                if stats["total"] > 0
                else None
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

    except Exception as e:
        logger.error(f"Failed to compute per-pillar accuracy: {e}")
        raise HTTPException(
            status_code=500, detail=_safe_error("per-pillar accuracy", e)
        ) from e
