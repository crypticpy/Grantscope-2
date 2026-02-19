#!/usr/bin/env python3
"""Deprecated migration helper.

This script intentionally does not execute SQL.
Use the canonical migration runner instead:

    ./infra/migrate.sh
"""

import sys


def main() -> int:
    print("backend/run_migration.py is deprecated and intentionally does not run SQL.")
    print("Use ./infra/migrate.sh from the repository root.")
    print("One-off SQL should be added to supabase/migrations/ as an immutable file.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
