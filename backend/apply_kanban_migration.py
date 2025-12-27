#!/usr/bin/env python3
"""
Apply the workstream kanban migration to Supabase.
Uses the Supabase Management API to execute SQL.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    exit(1)

# Extract project ref from URL
project_ref = SUPABASE_URL.replace("https://", "").replace(".supabase.co", "")

# Migration SQL - split into individual statements
migration_statements = [
    # Add status column
    """
    ALTER TABLE workstream_cards
    ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'inbox'
        CHECK (status IN ('inbox', 'screening', 'research', 'brief', 'watching', 'archived'))
    """,

    # Add position column
    """
    ALTER TABLE workstream_cards
    ADD COLUMN IF NOT EXISTS position INTEGER DEFAULT 0
    """,

    # Add notes column
    """
    ALTER TABLE workstream_cards
    ADD COLUMN IF NOT EXISTS notes TEXT
    """,

    # Add reminder_at column
    """
    ALTER TABLE workstream_cards
    ADD COLUMN IF NOT EXISTS reminder_at TIMESTAMPTZ
    """,

    # Add added_from column
    """
    ALTER TABLE workstream_cards
    ADD COLUMN IF NOT EXISTS added_from TEXT DEFAULT 'manual'
        CHECK (added_from IN ('manual', 'auto', 'follow'))
    """,

    # Add updated_at column
    """
    ALTER TABLE workstream_cards
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()
    """,
]

# Index statements
index_statements = [
    """
    CREATE INDEX IF NOT EXISTS idx_workstream_cards_status
    ON workstream_cards(workstream_id, status)
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_workstream_cards_position
    ON workstream_cards(workstream_id, status, position)
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_workstream_cards_reminder
    ON workstream_cards(reminder_at)
    WHERE reminder_at IS NOT NULL
    """,
]

# Trigger statements
trigger_statements = [
    """
    DROP TRIGGER IF EXISTS trigger_workstream_cards_updated_at ON workstream_cards
    """,

    """
    CREATE TRIGGER trigger_workstream_cards_updated_at
        BEFORE UPDATE ON workstream_cards
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at()
    """,
]

def execute_sql_via_rest(sql: str) -> dict:
    """Execute SQL via Supabase REST API using rpc."""
    # Use the postgrest-compatible endpoint
    url = f"{SUPABASE_URL}/rest/v1/rpc/execute_sql"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, json={"sql": sql}, headers=headers)
    return response


print("Applying workstream kanban migration...")
print("=" * 50)

# Since direct SQL execution isn't available via REST, output SQL for manual execution
print("\nPlease run the following SQL in the Supabase SQL Editor:")
print("Go to: https://supabase.com/dashboard/project/" + project_ref + "/sql/new")
print("\n" + "=" * 50 + "\n")

# Combine all statements
all_sql = """
-- Migration: workstream_kanban
-- Purpose: Add kanban board columns to workstream_cards table

-- Add columns
ALTER TABLE workstream_cards
ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'inbox'
    CHECK (status IN ('inbox', 'screening', 'research', 'brief', 'watching', 'archived'));

ALTER TABLE workstream_cards
ADD COLUMN IF NOT EXISTS position INTEGER DEFAULT 0;

ALTER TABLE workstream_cards
ADD COLUMN IF NOT EXISTS notes TEXT;

ALTER TABLE workstream_cards
ADD COLUMN IF NOT EXISTS reminder_at TIMESTAMPTZ;

ALTER TABLE workstream_cards
ADD COLUMN IF NOT EXISTS added_from TEXT DEFAULT 'manual'
    CHECK (added_from IN ('manual', 'auto', 'follow'));

ALTER TABLE workstream_cards
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_workstream_cards_status
ON workstream_cards(workstream_id, status);

CREATE INDEX IF NOT EXISTS idx_workstream_cards_position
ON workstream_cards(workstream_id, status, position);

CREATE INDEX IF NOT EXISTS idx_workstream_cards_reminder
ON workstream_cards(reminder_at)
WHERE reminder_at IS NOT NULL;

-- Create trigger
DROP TRIGGER IF EXISTS trigger_workstream_cards_updated_at ON workstream_cards;

CREATE TRIGGER trigger_workstream_cards_updated_at
    BEFORE UPDATE ON workstream_cards
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Verify
SELECT column_name FROM information_schema.columns
WHERE table_name = 'workstream_cards'
ORDER BY ordinal_position;
"""

print(all_sql)
print("\n" + "=" * 50)
print("\nAfter running the SQL, refresh your browser to test the kanban board.")
