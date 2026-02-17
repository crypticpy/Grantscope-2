"""Business logic for the Application Materials Checklist feature."""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.checklist import ChecklistItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category keyword mapping for auto-extraction
# ---------------------------------------------------------------------------
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "budget": ["budget", "cost", "financial", "funding"],
    "narrative": [
        "narrative",
        "abstract",
        "summary",
        "statement of need",
        "project description",
    ],
    "staffing": [
        "resume",
        "cv",
        "curriculum vitae",
        "personnel",
        "staffing",
        "key personnel",
        "biographical sketch",
    ],
    "timeline": ["timeline", "schedule", "milestones", "work plan", "gantt"],
    "evaluation": [
        "evaluation",
        "metrics",
        "outcomes",
        "performance measure",
        "logic model",
    ],
    "registration": ["registration", "sam.gov", "duns", "uei", "grants.gov"],
    "legal": [
        "legal",
        "compliance",
        "assurance",
        "certification",
        "lobbying",
        "debarment",
    ],
    "organizational": [
        "org chart",
        "organizational",
        "organization chart",
        "governance",
        "board",
    ],
}

# ---------------------------------------------------------------------------
# Standard suggestions by grant type
# ---------------------------------------------------------------------------
_FEDERAL_SUGGESTIONS: list[dict[str, str]] = [
    {"description": "SAM.gov active registration", "category": "registration"},
    {"description": "Indirect cost rate agreement", "category": "budget"},
    {"description": "Audit report (if >$750K)", "category": "legal"},
    {"description": "Data management plan", "category": "narrative"},
    {"description": "Budget narrative", "category": "budget"},
    {"description": "Key personnel resumes", "category": "staffing"},
]

_STATE_LOCAL_SUGGESTIONS: list[dict[str, str]] = [
    {"description": "Letter of support from leadership", "category": "organizational"},
    {"description": "Org chart", "category": "organizational"},
    {"description": "Proof of nonprofit status (if applicable)", "category": "legal"},
]


def _classify_category(requirement_text: str) -> str:
    """Map a requirement string to a checklist category using keyword matching."""
    lower = requirement_text.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return category
    return "other"


class ChecklistService:
    """Service layer for checklist operations."""

    @staticmethod
    async def auto_create_from_grant(
        db: AsyncSession,
        application_id: UUID,
        grant_context: dict,
    ) -> list[ChecklistItem]:
        """Parse grant_context requirements and create checklist items.

        Args:
            db: Async database session.
            application_id: UUID of the grant application.
            grant_context: Dict containing a ``requirements`` list of strings.

        Returns:
            List of newly created ChecklistItem rows.
        """
        requirements: list[str] = grant_context.get("requirements", [])
        if not requirements:
            return []

        created: list[ChecklistItem] = []
        for idx, req_text in enumerate(requirements):
            if not req_text or not req_text.strip():
                continue
            item = ChecklistItem(
                application_id=application_id,
                category=_classify_category(req_text),
                description=req_text.strip(),
                is_mandatory=True,
                source="extracted",
                sort_order=idx,
            )
            db.add(item)
            created.append(item)

        if created:
            await db.flush()
            for item in created:
                await db.refresh(item)

        return created

    @staticmethod
    async def ai_suggest_items(
        db: AsyncSession,
        application_id: UUID,
        grant_type: str | None = None,
    ) -> list[ChecklistItem]:
        """Suggest standard checklist items based on grant type.

        Checks which items already exist to avoid duplicates, then creates
        new items with ``source='ai_suggested'`` and ``is_mandatory=False``.

        Args:
            db: Async database session.
            application_id: UUID of the grant application.
            grant_type: Optional grant type hint (e.g. 'federal', 'state', 'local').

        Returns:
            List of newly created ChecklistItem rows.
        """
        # Determine which suggestions to use
        normalized_type = (grant_type or "federal").lower().strip()
        if normalized_type in ("state", "local", "state/local"):
            suggestions = _STATE_LOCAL_SUGGESTIONS
        else:
            # Default to federal suggestions
            suggestions = _FEDERAL_SUGGESTIONS

        # Fetch existing item descriptions to avoid duplicates
        result = await db.execute(
            select(ChecklistItem.description).where(
                ChecklistItem.application_id == application_id
            )
        )
        existing_descriptions = {row[0].lower() for row in result.all()}

        created: list[ChecklistItem] = []
        # Start sort_order after existing items
        existing_count_result = await db.execute(
            select(ChecklistItem.sort_order).where(
                ChecklistItem.application_id == application_id
            )
        )
        existing_orders = [row[0] for row in existing_count_result.all()]
        next_sort = (max(existing_orders) + 1) if existing_orders else 0

        for suggestion in suggestions:
            if suggestion["description"].lower() in existing_descriptions:
                continue
            item = ChecklistItem(
                application_id=application_id,
                category=suggestion["category"],
                description=suggestion["description"],
                is_mandatory=False,
                source="ai_suggested",
                sort_order=next_sort,
            )
            db.add(item)
            created.append(item)
            next_sort += 1

        if created:
            await db.flush()
            for item in created:
                await db.refresh(item)

        return created

    @staticmethod
    async def auto_complete_check(
        db: AsyncSession,
        application_id: UUID,
        existing_sections: list[str] | None = None,
        attachment_categories: list[str] | None = None,
    ) -> int:
        """Auto-mark checklist items as completed based on existing work.

        Matches section names and attachment categories against incomplete
        checklist item descriptions using keyword overlap.

        Args:
            db: Async database session.
            application_id: UUID of the grant application.
            existing_sections: List of proposal section keys that already exist.
            attachment_categories: List of attachment category strings.

        Returns:
            Count of items auto-completed.
        """
        sections = [s.lower().replace("_", " ") for s in (existing_sections or [])]
        attachments = [
            a.lower().replace("_", " ") for a in (attachment_categories or [])
        ]
        all_evidence = sections + attachments

        if not all_evidence:
            return 0

        # Fetch incomplete items
        result = await db.execute(
            select(ChecklistItem).where(
                ChecklistItem.application_id == application_id,
                ChecklistItem.is_completed.is_(False),
            )
        )
        items = list(result.scalars().all())

        completed_count = 0
        from sqlalchemy import func

        for item in items:
            desc_lower = item.description.lower()
            # Check if any evidence string overlaps with the item description
            for evidence in all_evidence:
                # Match if the evidence keyword appears in the description
                # or if a significant word from the description appears in the evidence
                desc_words = {w for w in desc_lower.split() if len(w) > 3}
                evidence_words = {w for w in evidence.split() if len(w) > 3}
                if (
                    evidence in desc_lower
                    or desc_lower in evidence
                    or (desc_words & evidence_words)
                ):
                    item.is_completed = True
                    item.completed_at = func.now()
                    completed_count += 1
                    break

        if completed_count:
            await db.flush()

        return completed_count
