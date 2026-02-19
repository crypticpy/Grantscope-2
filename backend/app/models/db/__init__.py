"""SQLAlchemy 2.0 ORM models for GrantScope2.

Import all models here so Alembic's ``env.py`` can discover them via::

    from app.models.db import Base  # noqa: F401

Every model must be imported at module level to register with the
``DeclarativeBase`` metadata.
"""

from app.models.db.base import Base, TimestampMixin  # noqa: F401

# Reference tables
from app.models.db.reference import (  # noqa: F401
    Anchor,
    Department,
    Goal,
    GrantCategory,
    Pillar,
    Priority,
    Stage,
)

# Core domain models
from app.models.db.user import User  # noqa: F401
from app.models.db.card import Card, CardEmbedding  # noqa: F401
from app.models.db.source import (  # noqa: F401
    DiscoveredSource,
    Source,
    SignalSource,
    SourceRating,
)
from app.models.db.workstream import (  # noqa: F401
    Workstream,
    WorkstreamCard,
    WorkstreamScan,
)
from app.models.db.proposal import Proposal  # noqa: F401
from app.models.db.wizard_session import WizardSession  # noqa: F401
from app.models.db.grant_application import GrantApplication  # noqa: F401
from app.models.db.chat import (  # noqa: F401
    ChatConversation,
    ChatMessage,
    ChatPinnedMessage,
)
from app.models.db.discovery import (  # noqa: F401
    DiscoveryBlock,
    DiscoveryRun,
    DiscoverySchedule,
    UserCardDismissal,
)

# Supporting tables
from app.models.db.card_extras import (  # noqa: F401
    CardFollow,
    CardNote,
    CardRelationship,
    CardScoreHistory,
    CardSnapshot,
    CardTimeline,
    Entity,
    EntityRelationship,
    ImplicationsAnalysis,
    Implication,
    UserSignalPreference,
)
from app.models.db.brief import ExecutiveBrief  # noqa: F401
from app.models.db.research import ResearchTask  # noqa: F401
from app.models.db.analytics import (  # noqa: F401
    CachedInsight,
    ClassificationValidation,
    DomainReputation,
    PatternInsight,
)
from app.models.db.search import SavedSearch, SearchHistory  # noqa: F401
from app.models.db.notification import (  # noqa: F401
    DigestLog,
    NotificationPreference,
)
from app.models.db.rss import RssFeed, RssFeedItem  # noqa: F401

# New feature tables (Phase 3)
from app.models.db.checklist import ChecklistItem  # noqa: F401
from app.models.db.budget import BudgetLineItem, BudgetSettings  # noqa: F401
from app.models.db.attachment import ApplicationAttachment  # noqa: F401
from app.models.db.collaboration import (  # noqa: F401
    ApplicationCollaborator,
    ApplicationComment,
)
from app.models.db.milestone import (  # noqa: F401
    ApplicationMilestone,
    ApplicationStatusHistory,
)
from app.models.db.card_document import CardDocument  # noqa: F401
from app.models.db.system_settings import SystemSetting  # noqa: F401

__all__ = [
    "Base",
    "TimestampMixin",
    # Reference
    "Anchor",
    "Department",
    "Goal",
    "GrantCategory",
    "Pillar",
    "Priority",
    "Stage",
    # Core
    "User",
    "Card",
    "Source",
    "DiscoveredSource",
    "SignalSource",
    "SourceRating",
    "Workstream",
    "WorkstreamCard",
    "WorkstreamScan",
    "Proposal",
    "WizardSession",
    "GrantApplication",
    "ChatConversation",
    "ChatMessage",
    "ChatPinnedMessage",
    "DiscoveryBlock",
    "DiscoveryRun",
    "DiscoverySchedule",
    "UserCardDismissal",
    # Supporting
    "CardFollow",
    "CardNote",
    "CardRelationship",
    "CardScoreHistory",
    "CardSnapshot",
    "CardTimeline",
    "Entity",
    "EntityRelationship",
    "ImplicationsAnalysis",
    "Implication",
    "UserSignalPreference",
    "ExecutiveBrief",
    "ResearchTask",
    "CachedInsight",
    "DomainReputation",
    "PatternInsight",
    "DigestLog",
    "NotificationPreference",
    "RssFeed",
    "RssFeedItem",
    # New feature tables
    "ChecklistItem",
    "BudgetLineItem",
    "BudgetSettings",
    "ApplicationAttachment",
    "ApplicationCollaborator",
    "ApplicationComment",
    "ApplicationMilestone",
    "ApplicationStatusHistory",
    "CardDocument",
    # Migration additions
    "CardEmbedding",
    "ClassificationValidation",
    "SavedSearch",
    "SearchHistory",
    "SystemSetting",
]
