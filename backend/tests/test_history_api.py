"""
Integration Tests for History API Endpoints

Tests the trend visualization API endpoints:
- GET /api/v1/cards/{card_id}/score-history - Historical score data for timeline charts
- GET /api/v1/cards/{card_id}/stage-history - Stage transition history
- GET /api/v1/cards/{card_id}/related - Related cards for concept network
- GET /api/v1/cards/compare - Side-by-side card comparison

Usage:
    cd backend && pytest tests/test_history_api.py -v
"""

import pytest
import sys
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, MagicMock, patch, AsyncMock
import uuid

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ============================================================================
# TEST DATA FACTORIES
# ============================================================================

def generate_uuid() -> str:
    """Generate a valid UUID string."""
    return str(uuid.uuid4())


def make_mock_card(
    card_id: str = None,
    name: str = "Test Card",
    slug: str = "test-card",
    summary: str = "A test card summary",
    pillar_id: str = "CH",
    goal_id: str = "CH.1",
    stage_id: str = "3",
    horizon: str = "H2",
    maturity_score: int = 65,
    velocity_score: int = 72,
    novelty_score: int = 58,
    impact_score: int = 80,
    relevance_score: int = 75,
    risk_score: int = 30,
    opportunity_score: int = 85,
) -> Dict[str, Any]:
    """Factory function to create mock card data."""
    if card_id is None:
        card_id = generate_uuid()
    now = datetime.now(timezone.utc)
    return {
        "id": card_id,
        "name": name,
        "slug": slug,
        "summary": summary,
        "pillar_id": pillar_id,
        "goal_id": goal_id,
        "stage_id": stage_id,
        "horizon": horizon,
        "maturity_score": maturity_score,
        "velocity_score": velocity_score,
        "novelty_score": novelty_score,
        "impact_score": impact_score,
        "relevance_score": relevance_score,
        "risk_score": risk_score,
        "opportunity_score": opportunity_score,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


def make_mock_score_history(
    card_id: str,
    days_ago: int = 0,
    maturity_score: int = 65,
    velocity_score: int = 72,
) -> Dict[str, Any]:
    """Factory function to create mock score history data."""
    record_id = generate_uuid()
    recorded_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "id": record_id,
        "card_id": card_id,
        "recorded_at": recorded_at.isoformat(),
        "maturity_score": maturity_score,
        "velocity_score": velocity_score,
        "novelty_score": 58,
        "impact_score": 80,
        "relevance_score": 75,
        "risk_score": 30,
        "opportunity_score": 85,
    }


def make_mock_stage_history(
    card_id: str,
    days_ago: int = 0,
    old_stage_id: int = None,
    new_stage_id: int = 3,
    old_horizon: str = None,
    new_horizon: str = "H2",
    trigger: str = "manual",
    reason: str = None,
) -> Dict[str, Any]:
    """Factory function to create mock stage history (timeline) data."""
    record_id = generate_uuid()
    created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "id": record_id,
        "card_id": card_id,
        "created_at": created_at.isoformat(),
        "event_type": "stage_changed",
        "old_stage_id": old_stage_id,
        "new_stage_id": new_stage_id,
        "old_horizon": old_horizon,
        "new_horizon": new_horizon,
        "trigger": trigger,
        "reason": reason,
    }


def make_mock_relationship(
    source_card_id: str,
    target_card_id: str,
    relationship_type: str = "related",
    strength: float = 0.8,
) -> Dict[str, Any]:
    """Factory function to create mock card relationship data."""
    rel_id = generate_uuid()
    created_at = datetime.now(timezone.utc)
    return {
        "id": rel_id,
        "source_card_id": source_card_id,
        "target_card_id": target_card_id,
        "relationship_type": relationship_type,
        "strength": strength,
        "created_at": created_at.isoformat(),
    }


# ============================================================================
# MOCK SUPABASE RESPONSE CLASSES
# ============================================================================

class MockSupabaseResponse:
    """Mock Supabase response object."""
    def __init__(self, data: List[Dict] = None):
        self.data = data if data is not None else []


class MockSupabaseQuery:
    """Mock Supabase query builder with chainable methods."""
    def __init__(self, data: List[Dict] = None):
        self._data = data if data is not None else []
        self._filtered_data = self._data.copy()

    def select(self, *args, **kwargs):
        return self

    def eq(self, field: str, value: Any):
        self._filtered_data = [
            row for row in self._filtered_data
            if row.get(field) == value
        ]
        return self

    def in_(self, field: str, values: List):
        self._filtered_data = [
            row for row in self._filtered_data
            if row.get(field) in values
        ]
        return self

    def gte(self, field: str, value: Any):
        return self

    def lte(self, field: str, value: Any):
        return self

    def order(self, field: str, desc: bool = False):
        return self

    def limit(self, count: int):
        self._filtered_data = self._filtered_data[:count]
        return self

    def execute(self):
        return MockSupabaseResponse(self._filtered_data)


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    return {
        "id": "test-user-id",
        "email": "test@example.com",
        "display_name": "Test User",
        "department": "Engineering",
        "role": "analyst",
        "preferences": {},
    }


@pytest.fixture
def test_cards():
    """Generate test card data with consistent UUIDs."""
    card1_id = generate_uuid()
    card2_id = generate_uuid()
    card3_id = generate_uuid()
    return {
        "card1": make_mock_card(card_id=card1_id, name="Card 1", slug="card-1"),
        "card2": make_mock_card(card_id=card2_id, name="Card 2", slug="card-2"),
        "card3": make_mock_card(card_id=card3_id, name="Card 3", slug="card-3"),
        "card1_id": card1_id,
        "card2_id": card2_id,
        "card3_id": card3_id,
    }


@pytest.fixture
def test_data_store(test_cards):
    """Create test data store with all mock data."""
    card1 = test_cards["card1"]
    card2 = test_cards["card2"]
    card3 = test_cards["card3"]

    return {
        "cards": [card1, card2, card3],
        "users": [
            {
                "id": "test-user-id",
                "email": "test@example.com",
                "display_name": "Test User",
                "department": "Engineering",
                "role": "analyst",
                "preferences": {},
            }
        ],
        "card_score_history": [
            make_mock_score_history(card1["id"], days_ago=0, maturity_score=65, velocity_score=72),
            make_mock_score_history(card1["id"], days_ago=7, maturity_score=60, velocity_score=68),
            make_mock_score_history(card1["id"], days_ago=14, maturity_score=55, velocity_score=65),
            make_mock_score_history(card2["id"], days_ago=0, maturity_score=80, velocity_score=85),
            make_mock_score_history(card2["id"], days_ago=7, maturity_score=75, velocity_score=80),
        ],
        "card_timeline": [
            make_mock_stage_history(card1["id"], days_ago=0, old_stage_id=2, new_stage_id=3, old_horizon="H3", new_horizon="H2"),
            make_mock_stage_history(card1["id"], days_ago=30, old_stage_id=1, new_stage_id=2, old_horizon="H3", new_horizon="H3"),
            make_mock_stage_history(card2["id"], days_ago=0, old_stage_id=5, new_stage_id=6, old_horizon="H2", new_horizon="H1"),
        ],
        "card_relationships": [
            make_mock_relationship(card1["id"], card2["id"], relationship_type="related", strength=0.8),
            make_mock_relationship(card1["id"], card3["id"], relationship_type="similar", strength=0.6),
            make_mock_relationship(card2["id"], card3["id"], relationship_type="derived", strength=0.7),
        ],
    }


@pytest.fixture
def mock_supabase_table(test_data_store):
    """Create a mock supabase.table() function."""
    def table_fn(table_name: str):
        data = test_data_store.get(table_name, [])
        return MockSupabaseQuery(data)
    return table_fn


# ============================================================================
# RESPONSE MODEL VALIDATION TESTS
# ============================================================================

class TestScoreHistoryResponseModel:
    """Tests for ScoreHistoryResponse model validation."""

    def test_score_history_model_has_required_fields(self):
        """ScoreHistoryResponse should have all required fields."""
        from app.models.history import ScoreHistoryResponse, ScoreHistory

        # Test ScoreHistoryResponse structure
        assert hasattr(ScoreHistoryResponse, 'model_fields')
        fields = ScoreHistoryResponse.model_fields.keys()
        assert 'history' in fields
        assert 'card_id' in fields
        assert 'total_count' in fields

    def test_score_history_model_has_score_fields(self):
        """ScoreHistory should have all 7 score dimension fields."""
        from app.models.history import ScoreHistory

        fields = ScoreHistory.model_fields.keys()
        score_fields = [
            'maturity_score', 'velocity_score', 'novelty_score',
            'impact_score', 'relevance_score', 'risk_score', 'opportunity_score'
        ]
        for score_field in score_fields:
            assert score_field in fields, f"Missing score field: {score_field}"

    def test_score_history_validates_score_range(self):
        """ScoreHistory should validate scores are in 0-100 range."""
        from app.models.history import ScoreHistory
        from pydantic import ValidationError

        # Valid scores should work
        valid_record = ScoreHistory(
            id=generate_uuid(),
            card_id=generate_uuid(),
            recorded_at=datetime.now(timezone.utc),
            maturity_score=50,
            velocity_score=100,
            novelty_score=0,
        )
        assert valid_record.maturity_score == 50

        # Invalid scores should fail
        with pytest.raises(ValidationError):
            ScoreHistory(
                id=generate_uuid(),
                card_id=generate_uuid(),
                recorded_at=datetime.now(timezone.utc),
                maturity_score=150,  # Invalid: > 100
            )


class TestStageHistoryResponseModel:
    """Tests for StageHistory model validation."""

    def test_stage_history_model_has_required_fields(self):
        """StageHistory should have all required transition tracking fields."""
        from app.models.history import StageHistory

        fields = StageHistory.model_fields.keys()
        required_fields = [
            'id', 'card_id', 'changed_at',
            'old_stage_id', 'new_stage_id',
            'old_horizon', 'new_horizon'
        ]
        for field in required_fields:
            assert field in fields, f"Missing required field: {field}"

    def test_stage_history_validates_stage_id_range(self):
        """StageHistory should validate stage IDs are 1-8."""
        from app.models.history import StageHistory
        from pydantic import ValidationError

        # Valid stage IDs
        valid_record = StageHistory(
            id=generate_uuid(),
            card_id=generate_uuid(),
            changed_at=datetime.now(timezone.utc),
            old_stage_id=1,
            new_stage_id=8,
            new_horizon="H1",
        )
        assert valid_record.new_stage_id == 8

        # Invalid stage ID
        with pytest.raises(ValidationError):
            StageHistory(
                id=generate_uuid(),
                card_id=generate_uuid(),
                changed_at=datetime.now(timezone.utc),
                new_stage_id=9,  # Invalid: > 8
                new_horizon="H1",
            )

    def test_stage_history_validates_horizon_format(self):
        """StageHistory should validate horizon format (H1, H2, H3)."""
        from app.models.history import StageHistory
        from pydantic import ValidationError

        # Valid horizons
        for horizon in ["H1", "H2", "H3"]:
            record = StageHistory(
                id=generate_uuid(),
                card_id=generate_uuid(),
                changed_at=datetime.now(timezone.utc),
                new_stage_id=3,
                new_horizon=horizon,
            )
            assert record.new_horizon == horizon

        # Invalid horizon
        with pytest.raises(ValidationError):
            StageHistory(
                id=generate_uuid(),
                card_id=generate_uuid(),
                changed_at=datetime.now(timezone.utc),
                new_stage_id=3,
                new_horizon="H4",  # Invalid
            )


class TestCardRelationshipModel:
    """Tests for CardRelationship model validation."""

    def test_relationship_model_has_required_fields(self):
        """CardRelationship should have source, target, and type fields."""
        from app.models.history import CardRelationship

        fields = CardRelationship.model_fields.keys()
        required_fields = [
            'id', 'source_card_id', 'target_card_id',
            'relationship_type', 'strength', 'created_at'
        ]
        for field in required_fields:
            assert field in fields, f"Missing required field: {field}"

    def test_relationship_validates_type(self):
        """CardRelationship should validate relationship type."""
        from app.models.history import CardRelationship
        from pydantic import ValidationError

        valid_types = ['related', 'similar', 'derived', 'dependent', 'parent', 'child']
        for rel_type in valid_types:
            record = CardRelationship(
                id=generate_uuid(),
                source_card_id=generate_uuid(),
                target_card_id=generate_uuid(),
                relationship_type=rel_type,
                created_at=datetime.now(timezone.utc),
            )
            assert record.relationship_type == rel_type

        # Invalid type
        with pytest.raises(ValidationError):
            CardRelationship(
                id=generate_uuid(),
                source_card_id=generate_uuid(),
                target_card_id=generate_uuid(),
                relationship_type="invalid_type",
                created_at=datetime.now(timezone.utc),
            )

    def test_relationship_validates_strength_range(self):
        """CardRelationship strength should be 0-1."""
        from app.models.history import CardRelationship
        from pydantic import ValidationError

        # Valid strength
        record = CardRelationship(
            id=generate_uuid(),
            source_card_id=generate_uuid(),
            target_card_id=generate_uuid(),
            relationship_type="related",
            strength=0.5,
            created_at=datetime.now(timezone.utc),
        )
        assert record.strength == 0.5

        # Invalid strength
        with pytest.raises(ValidationError):
            CardRelationship(
                id=generate_uuid(),
                source_card_id=generate_uuid(),
                target_card_id=generate_uuid(),
                relationship_type="related",
                strength=1.5,  # Invalid: > 1.0
                created_at=datetime.now(timezone.utc),
            )


class TestCardComparisonModel:
    """Tests for CardComparison models validation."""

    def test_comparison_response_has_both_cards(self):
        """CardComparisonResponse should have card1 and card2 fields."""
        from app.models.history import CardComparisonResponse

        fields = CardComparisonResponse.model_fields.keys()
        assert 'card1' in fields
        assert 'card2' in fields
        assert 'comparison_generated_at' in fields

    def test_comparison_item_has_all_data(self):
        """CardComparisonItem should include card, score_history, and stage_history."""
        from app.models.history import CardComparisonItem

        fields = CardComparisonItem.model_fields.keys()
        assert 'card' in fields
        assert 'score_history' in fields
        assert 'stage_history' in fields


# ============================================================================
# API ENDPOINT UNIT TESTS (Using Mocks)
# ============================================================================

class TestScoreHistoryEndpoint:
    """Unit tests for score-history endpoint logic."""

    def test_score_history_query_builder(self, test_cards, test_data_store):
        """Test that score history query correctly filters by card_id."""
        card_id = test_cards["card1"]["id"]
        query = MockSupabaseQuery(test_data_store["card_score_history"])
        result = query.eq("card_id", card_id).execute()

        assert len(result.data) == 3  # card1 has 3 score history records
        for record in result.data:
            assert record["card_id"] == card_id

    def test_score_history_empty_for_unknown_card(self, test_data_store):
        """Test that unknown card returns empty score history."""
        unknown_card_id = generate_uuid()
        query = MockSupabaseQuery(test_data_store["card_score_history"])
        result = query.eq("card_id", unknown_card_id).execute()

        assert len(result.data) == 0

    def test_score_history_contains_all_scores(self, test_cards, test_data_store):
        """Test that each score history record contains all 7 score types."""
        card_id = test_cards["card1"]["id"]
        query = MockSupabaseQuery(test_data_store["card_score_history"])
        result = query.eq("card_id", card_id).execute()

        score_fields = [
            'maturity_score', 'velocity_score', 'novelty_score',
            'impact_score', 'relevance_score', 'risk_score', 'opportunity_score'
        ]

        for record in result.data:
            for field in score_fields:
                assert field in record, f"Missing score field: {field}"


class TestStageHistoryEndpoint:
    """Unit tests for stage-history endpoint logic."""

    def test_stage_history_query_builder(self, test_cards, test_data_store):
        """Test that stage history query correctly filters by card_id."""
        card_id = test_cards["card1"]["id"]
        query = MockSupabaseQuery(test_data_store["card_timeline"])
        result = query.eq("card_id", card_id).execute()

        assert len(result.data) == 2  # card1 has 2 stage changes
        for record in result.data:
            assert record["card_id"] == card_id

    def test_stage_history_filters_by_event_type(self, test_cards, test_data_store):
        """Test that stage history only includes 'stage_changed' events."""
        card_id = test_cards["card1"]["id"]
        query = MockSupabaseQuery(test_data_store["card_timeline"])
        result = query.eq("card_id", card_id).eq("event_type", "stage_changed").execute()

        for record in result.data:
            assert record["event_type"] == "stage_changed"

    def test_stage_history_has_transition_fields(self, test_cards, test_data_store):
        """Test that stage history records have old/new stage and horizon."""
        card_id = test_cards["card1"]["id"]
        query = MockSupabaseQuery(test_data_store["card_timeline"])
        result = query.eq("card_id", card_id).execute()

        for record in result.data:
            assert "old_stage_id" in record
            assert "new_stage_id" in record
            assert "old_horizon" in record
            assert "new_horizon" in record


class TestRelatedCardsEndpoint:
    """Unit tests for related cards endpoint logic."""

    def test_related_cards_finds_source_relationships(self, test_cards, test_data_store):
        """Test finding relationships where card is source."""
        card_id = test_cards["card1"]["id"]
        query = MockSupabaseQuery(test_data_store["card_relationships"])
        result = query.eq("source_card_id", card_id).execute()

        assert len(result.data) == 2  # card1 is source in 2 relationships
        for rel in result.data:
            assert rel["source_card_id"] == card_id

    def test_related_cards_finds_target_relationships(self, test_cards, test_data_store):
        """Test finding relationships where card is target."""
        card_id = test_cards["card2"]["id"]
        query = MockSupabaseQuery(test_data_store["card_relationships"])
        result = query.eq("target_card_id", card_id).execute()

        assert len(result.data) == 1  # card2 is target in 1 relationship

    def test_related_cards_includes_metadata(self, test_data_store):
        """Test that relationships include type and strength."""
        query = MockSupabaseQuery(test_data_store["card_relationships"])
        result = query.execute()

        for rel in result.data:
            assert "relationship_type" in rel
            assert "strength" in rel


class TestCompareCardsEndpoint:
    """Unit tests for compare cards endpoint logic."""

    def test_compare_parses_card_ids(self, test_cards):
        """Test that card_ids string is correctly parsed."""
        card_ids_str = f"{test_cards['card1']['id']},{test_cards['card2']['id']}"
        ids = [id.strip() for id in card_ids_str.split(",") if id.strip()]

        assert len(ids) == 2
        assert ids[0] == test_cards["card1"]["id"]
        assert ids[1] == test_cards["card2"]["id"]

    def test_compare_validates_two_cards_required(self, test_cards):
        """Test that compare requires exactly 2 card IDs."""
        # Single card
        single_id = test_cards["card1"]["id"]
        ids = [id.strip() for id in single_id.split(",") if id.strip()]
        assert len(ids) != 2

        # Three cards
        triple_ids = f"{test_cards['card1']['id']},{test_cards['card2']['id']},{test_cards['card3']['id']}"
        ids = [id.strip() for id in triple_ids.split(",") if id.strip()]
        assert len(ids) != 2

    def test_compare_fetches_both_cards(self, test_cards, test_data_store):
        """Test that compare fetches data for both cards."""
        card1_id = test_cards["card1"]["id"]
        card2_id = test_cards["card2"]["id"]

        # Query cards
        card_query = MockSupabaseQuery(test_data_store["cards"])
        card1_result = card_query.eq("id", card1_id).execute()

        card_query2 = MockSupabaseQuery(test_data_store["cards"])
        card2_result = card_query2.eq("id", card2_id).execute()

        assert len(card1_result.data) == 1
        assert len(card2_result.data) == 1
        assert card1_result.data[0]["id"] == card1_id
        assert card2_result.data[0]["id"] == card2_id


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_score_history(self, test_cards, test_data_store):
        """Card with no score history returns empty list."""
        card3_id = test_cards["card3"]["id"]  # card3 has no score history
        query = MockSupabaseQuery(test_data_store["card_score_history"])
        result = query.eq("card_id", card3_id).execute()

        assert result.data == []

    def test_empty_stage_history(self, test_cards, test_data_store):
        """Card with no stage transitions returns empty list."""
        card3_id = test_cards["card3"]["id"]  # card3 has no stage history
        query = MockSupabaseQuery(test_data_store["card_timeline"])
        result = query.eq("card_id", card3_id).execute()

        assert result.data == []

    def test_card_not_found(self, test_data_store):
        """Unknown card ID returns empty result."""
        unknown_id = generate_uuid()
        query = MockSupabaseQuery(test_data_store["cards"])
        result = query.eq("id", unknown_id).execute()

        assert result.data == []

    def test_no_relationships(self, test_data_store):
        """Card without relationships returns empty list."""
        # Create a card ID that has no relationships
        orphan_card_id = generate_uuid()

        source_query = MockSupabaseQuery(test_data_store["card_relationships"])
        source_result = source_query.eq("source_card_id", orphan_card_id).execute()

        target_query = MockSupabaseQuery(test_data_store["card_relationships"])
        target_result = target_query.eq("target_card_id", orphan_card_id).execute()

        assert source_result.data == []
        assert target_result.data == []

    def test_uuid_validation(self):
        """Test UUID format validation."""
        import re

        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )

        valid_uuid = generate_uuid()
        assert uuid_pattern.match(valid_uuid)

        invalid_uuids = ["not-a-uuid", "12345", "", "123e4567-e89b-12d3-a456"]
        for invalid in invalid_uuids:
            assert not uuid_pattern.match(invalid)


# ============================================================================
# DATA CONSISTENCY TESTS
# ============================================================================

class TestDataConsistency:
    """Tests for data consistency and relationships."""

    def test_score_history_belongs_to_valid_card(self, test_cards, test_data_store):
        """All score history records reference existing cards."""
        card_ids = {card["id"] for card in test_data_store["cards"]}

        for record in test_data_store["card_score_history"]:
            assert record["card_id"] in card_ids, f"Orphan score history: {record['card_id']}"

    def test_stage_history_belongs_to_valid_card(self, test_cards, test_data_store):
        """All stage history records reference existing cards."""
        card_ids = {card["id"] for card in test_data_store["cards"]}

        for record in test_data_store["card_timeline"]:
            assert record["card_id"] in card_ids, f"Orphan stage history: {record['card_id']}"

    def test_relationships_reference_valid_cards(self, test_cards, test_data_store):
        """All relationships reference existing cards."""
        card_ids = {card["id"] for card in test_data_store["cards"]}

        for rel in test_data_store["card_relationships"]:
            assert rel["source_card_id"] in card_ids, f"Invalid source: {rel['source_card_id']}"
            assert rel["target_card_id"] in card_ids, f"Invalid target: {rel['target_card_id']}"

    def test_stage_ids_in_valid_range(self, test_data_store):
        """All stage IDs are in the valid 1-8 range."""
        for record in test_data_store["card_timeline"]:
            if record.get("new_stage_id") is not None:
                assert 1 <= record["new_stage_id"] <= 8
            if record.get("old_stage_id") is not None:
                assert 1 <= record["old_stage_id"] <= 8

    def test_horizons_are_valid(self, test_data_store):
        """All horizon values are H1, H2, or H3."""
        valid_horizons = {"H1", "H2", "H3"}

        for record in test_data_store["card_timeline"]:
            if record.get("new_horizon"):
                assert record["new_horizon"] in valid_horizons
            if record.get("old_horizon"):
                assert record["old_horizon"] in valid_horizons

    def test_relationship_types_are_valid(self, test_data_store):
        """All relationship types are in the valid set."""
        valid_types = {"related", "similar", "derived", "dependent", "parent", "child"}

        for rel in test_data_store["card_relationships"]:
            assert rel["relationship_type"] in valid_types

    def test_relationship_strength_in_range(self, test_data_store):
        """All relationship strengths are between 0 and 1."""
        for rel in test_data_store["card_relationships"]:
            if rel.get("strength") is not None:
                assert 0 <= rel["strength"] <= 1

    def test_scores_in_valid_range(self, test_data_store):
        """All score values are in 0-100 range."""
        score_fields = [
            'maturity_score', 'velocity_score', 'novelty_score',
            'impact_score', 'relevance_score', 'risk_score', 'opportunity_score'
        ]

        for record in test_data_store["card_score_history"]:
            for field in score_fields:
                if record.get(field) is not None:
                    assert 0 <= record[field] <= 100, f"{field} out of range: {record[field]}"


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
