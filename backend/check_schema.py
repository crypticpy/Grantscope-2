#!/usr/bin/env python3
"""
Schema validation script - compares database schema with code expectations.
"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

# Expected schema based on code usage
EXPECTED_SCHEMA = {
    "users": [
        "id", "email", "display_name", "department", "role",
        "preferences", "created_at", "updated_at"
    ],
    "cards": [
        "id", "name", "slug", "description", "summary",
        "horizon", "stage", "triage_score", "status",
        "pillars", "goals", "steep_categories", "anchors", "top25_relevance",
        "credibility_score", "novelty_score", "likelihood_score",
        "impact_score", "relevance_score",
        "time_to_awareness_months", "time_to_prepare_months",
        "velocity_score", "follower_count", "source_count",
        "embedding", "created_at", "updated_at", "created_by", "is_archived"
    ],
    "sources": [
        "id", "card_id", "url", "title", "publication", "author", "published_at",
        "api_source", "full_text", "ai_summary", "key_excerpts",
        "relevance_score", "relevance_to_card", "embedding",
        "ingested_at", "created_at"
    ],
    "card_timeline": [
        "id", "card_id", "event_type", "event_description",
        "previous_value", "new_value",
        "triggered_by_source_id", "triggered_by_user_id", "created_at"
    ],
    "workstreams": [
        "id", "user_id", "name", "description",
        "pillars", "goals", "anchors", "keywords",
        "min_stage", "max_stage", "horizons",
        "is_default", "notification_enabled", "created_at", "updated_at"
    ],
    "card_follows": [
        "id", "user_id", "card_id", "workstream_id", "followed_at", "created_at"
    ],
    "card_notes": [
        "id", "card_id", "user_id", "content", "is_private", "created_at", "updated_at"
    ],
    "pillars": [
        "code", "name", "description"
    ],
    "goals": [
        "code", "pillar_id", "name", "description", "sort_order"
    ],
    "anchors": [
        "id", "name", "description"
    ],
    "stages": [
        "id", "name", "horizon", "description", "sort_order"
    ],
    "research_tasks": [
        "id", "user_id", "card_id", "workstream_id",
        "task_type", "research_topic", "depth", "status",
        "created_at", "started_at", "completed_at",
        "result_summary", "error_message"
    ],
    "entities": [
        "id", "card_id", "source_id", "entity_type", "name",
        "description", "metadata", "created_at"
    ],
    "implications_analyses": [
        "id", "card_id", "perspective", "perspective_detail",
        "summary", "created_by", "created_at"
    ],
    "implications": [
        "id", "analysis_id", "parent_id", "order_level", "content",
        "likelihood_score", "desirability_score", "flag", "created_at"
    ]
}

def get_table_columns(table_name):
    """Get columns for a table using Supabase RPC or direct query."""
    try:
        # Try to select from the table with limit 0 to get structure
        result = supabase.table(table_name).select("*").limit(0).execute()
        # If we get here, table exists but we need columns
        # Try fetching one row to see columns
        result = supabase.table(table_name).select("*").limit(1).execute()
        if result.data:
            return list(result.data[0].keys())
        else:
            # Table exists but empty - try insert/error method
            return None
    except Exception as e:
        error_msg = str(e)
        if "does not exist" in error_msg or "PGRST200" in error_msg:
            return "TABLE_MISSING"
        return f"ERROR: {error_msg}"

def check_schema():
    """Check all tables and columns."""
    print("=" * 60)
    print("FORESIGHT DATABASE SCHEMA VALIDATION")
    print("=" * 60)

    missing_tables = []
    missing_columns = {}

    for table_name, expected_cols in EXPECTED_SCHEMA.items():
        print(f"\n📋 Checking table: {table_name}")

        actual_cols = get_table_columns(table_name)

        if actual_cols == "TABLE_MISSING":
            print(f"   ❌ TABLE MISSING!")
            missing_tables.append(table_name)
            continue
        elif isinstance(actual_cols, str) and actual_cols.startswith("ERROR"):
            print(f"   ⚠️  {actual_cols}")
            continue
        elif actual_cols is None:
            print(f"   ⚠️  Table exists but is empty (can't verify columns)")
            continue

        # Compare columns
        actual_set = set(actual_cols)
        expected_set = set(expected_cols)

        missing = expected_set - actual_set
        extra = actual_set - expected_set

        if missing:
            print(f"   ❌ Missing columns: {missing}")
            missing_columns[table_name] = list(missing)
        else:
            print(f"   ✅ All expected columns present")

        if extra:
            print(f"   ℹ️  Extra columns (OK): {extra}")

    # Generate fix SQL
    print("\n" + "=" * 60)
    print("SUMMARY & FIX SQL")
    print("=" * 60)

    if not missing_tables and not missing_columns:
        print("\n✅ All tables and columns are present!")
        return

    if missing_tables:
        print(f"\n❌ Missing tables: {missing_tables}")

    if missing_columns:
        print(f"\n❌ Missing columns by table:")
        for table, cols in missing_columns.items():
            print(f"   {table}: {cols}")

    # Generate ALTER statements
    print("\n📝 SQL to fix missing columns:")
    print("-" * 40)

    column_types = {
        "triggered_by_source_id": "UUID",
        "triggered_by_user_id": "UUID",
        "created_at": "TIMESTAMPTZ DEFAULT NOW()",
        "updated_at": "TIMESTAMPTZ DEFAULT NOW()",
        "followed_at": "TIMESTAMPTZ DEFAULT NOW()",
        "ingested_at": "TIMESTAMPTZ DEFAULT NOW()",
        "started_at": "TIMESTAMPTZ",
        "completed_at": "TIMESTAMPTZ",
        "published_at": "TIMESTAMPTZ",
        "id": "UUID PRIMARY KEY DEFAULT gen_random_uuid()",
        "user_id": "UUID",
        "card_id": "UUID",
        "source_id": "UUID",
        "workstream_id": "UUID",
        "analysis_id": "UUID",
        "parent_id": "UUID",
        "created_by": "UUID",
        "name": "TEXT",
        "title": "TEXT",
        "slug": "TEXT",
        "description": "TEXT",
        "summary": "TEXT",
        "content": "TEXT",
        "email": "TEXT",
        "display_name": "TEXT",
        "department": "TEXT",
        "role": "TEXT",
        "url": "TEXT",
        "publication": "TEXT",
        "author": "TEXT",
        "api_source": "TEXT",
        "full_text": "TEXT",
        "ai_summary": "TEXT",
        "event_type": "TEXT",
        "event_description": "TEXT",
        "task_type": "TEXT",
        "research_topic": "TEXT",
        "depth": "TEXT DEFAULT 'standard'",
        "status": "TEXT DEFAULT 'active'",
        "entity_type": "TEXT",
        "perspective": "TEXT",
        "perspective_detail": "TEXT",
        "error_message": "TEXT",
        "flag": "TEXT",
        "horizon": "TEXT",
        "code": "TEXT PRIMARY KEY",
        "pillar_id": "TEXT",
        "pillars": "TEXT[] DEFAULT '{}'",
        "goals": "TEXT[] DEFAULT '{}'",
        "anchors": "TEXT[] DEFAULT '{}'",
        "keywords": "TEXT[] DEFAULT '{}'",
        "horizons": "TEXT[] DEFAULT '{}'",
        "steep_categories": "TEXT[] DEFAULT '{}'",
        "top25_relevance": "TEXT[] DEFAULT '{}'",
        "key_excerpts": "TEXT[]",
        "preferences": "JSONB DEFAULT '{}'",
        "previous_value": "JSONB",
        "new_value": "JSONB",
        "result_summary": "JSONB",
        "metadata": "JSONB DEFAULT '{}'",
        "stage": "INTEGER",
        "triage_score": "INTEGER",
        "min_stage": "INTEGER",
        "max_stage": "INTEGER",
        "order_level": "INTEGER",
        "sort_order": "INTEGER DEFAULT 0",
        "follower_count": "INTEGER DEFAULT 0",
        "source_count": "INTEGER DEFAULT 0",
        "time_to_awareness_months": "INTEGER",
        "time_to_prepare_months": "INTEGER",
        "likelihood_score": "NUMERIC(3,2)",
        "desirability_score": "NUMERIC(3,2)",
        "credibility_score": "NUMERIC(3,2)",
        "novelty_score": "NUMERIC(3,2)",
        "impact_score": "NUMERIC(3,2)",
        "relevance_score": "NUMERIC(3,2)",
        "relevance_to_card": "NUMERIC(3,2)",
        "velocity_score": "NUMERIC(5,2) DEFAULT 0",
        "is_archived": "BOOLEAN DEFAULT FALSE",
        "is_private": "BOOLEAN DEFAULT FALSE",
        "is_default": "BOOLEAN DEFAULT FALSE",
        "notification_enabled": "BOOLEAN DEFAULT TRUE",
        "embedding": "VECTOR(1536)",
    }

    for table, cols in missing_columns.items():
        for col in cols:
            col_type = column_types.get(col, "TEXT")
            print(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type};")

if __name__ == "__main__":
    check_schema()
