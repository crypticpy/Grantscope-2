"""Shared helpers for admin sub-routers."""

import uuid as _uuid
from datetime import date, datetime
from decimal import Decimal


def _row_to_dict(obj, skip_cols=None) -> dict:
    """ORM row -> dict (safe JSON-serialisable conversion)."""
    skip = skip_cols or set()
    result = {}
    for col in obj.__table__.columns:
        if col.name in skip:
            continue
        value = getattr(obj, col.key, None)
        if isinstance(value, _uuid.UUID):
            result[col.name] = str(value)
        elif isinstance(value, (datetime, date)):
            result[col.name] = value.isoformat()
        elif isinstance(value, Decimal):
            result[col.name] = float(value)
        else:
            result[col.name] = value
    return result
