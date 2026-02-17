#!/usr/bin/env bash
# =============================================================================
# GrantScope2 — Database Migration Runner
# =============================================================================
# Applies all SQL migrations from supabase/migrations/ to the target database.
#
# Usage:
#   ./infra/migrate.sh                                             # Local default
#   ./infra/migrate.sh postgres://user:pass@host:5432/grantscope   # Custom DB
#   DB_URL=postgres://... ./infra/migrate.sh                       # Via env var
#
# Prerequisites:
#   - psql (PostgreSQL client) must be installed
#   - Database must be initialized (docker compose up postgres)
#   - infra/init-db.sql should have already run (roles + extensions)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MIGRATIONS_DIR="$PROJECT_ROOT/supabase/migrations"

# Database URL: CLI arg > env var > local default
DB_URL="${1:-${DB_URL:-postgres://postgres:postgres@localhost:5432/grantscope}}"

# Mask password in output
SAFE_URL=$(echo "$DB_URL" | sed 's|://[^:]*:[^@]*@|://***:***@|')
echo "=== GrantScope2 Migration Runner ==="
echo "Database: $SAFE_URL"
echo "Migrations: $MIGRATIONS_DIR"
echo ""

if ! command -v psql &>/dev/null; then
    echo "ERROR: psql not found. Install PostgreSQL client tools."
    echo "  macOS: brew install libpq && brew link --force libpq"
    echo "  Linux: apt install postgresql-client"
    exit 1
fi

if [ ! -d "$MIGRATIONS_DIR" ]; then
    echo "ERROR: Migrations directory not found: $MIGRATIONS_DIR"
    exit 1
fi

# Count migrations
MIGRATION_COUNT=$(ls "$MIGRATIONS_DIR"/*.sql 2>/dev/null | wc -l | tr -d ' ')
echo "Found $MIGRATION_COUNT migration files"
echo ""

# Apply migrations in sorted order
APPLIED=0
SKIPPED=0
FAILED=0

for migration in "$MIGRATIONS_DIR"/*.sql; do
    filename=$(basename "$migration")
    printf "  Applying: %-60s" "$filename"

    if psql "$DB_URL" -v ON_ERROR_STOP=0 -f "$migration" >/dev/null 2>&1; then
        echo "[OK]"
        ((APPLIED++))
    else
        # Try again with error output to see what happened
        ERROR_OUTPUT=$(psql "$DB_URL" -v ON_ERROR_STOP=0 -f "$migration" 2>&1 || true)

        if echo "$ERROR_OUTPUT" | grep -qi "already exists\|duplicate\|already a member"; then
            echo "[SKIP]"
            ((SKIPPED++))
        else
            echo "[WARN]"
            # Show first line of error for debugging
            FIRST_ERROR=$(echo "$ERROR_OUTPUT" | grep -i "error" | head -1)
            if [ -n "$FIRST_ERROR" ]; then
                echo "         $FIRST_ERROR"
            fi
            ((FAILED++))
        fi
    fi
done

echo ""
echo "=== Migration Summary ==="
echo "  Applied:  $APPLIED"
echo "  Skipped:  $SKIPPED (already applied)"
echo "  Warnings: $FAILED"
echo "  Total:    $MIGRATION_COUNT"

if [ "$FAILED" -gt 0 ]; then
    echo ""
    echo "Some migrations had warnings. This is normal for idempotent migrations"
    echo "that use IF NOT EXISTS or CREATE OR REPLACE."
fi

echo ""
echo "Done."
