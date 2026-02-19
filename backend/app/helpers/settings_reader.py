"""Cached reader for ``system_settings`` key-value configuration.

Provides :func:`get_setting` and :func:`get_settings_batch` to read
admin-configurable settings from the ``system_settings`` table with a
60-second in-memory cache.  The cache keeps repeated hot-path reads
(e.g. inside every chat request or scheduled job) from hitting the
database on every call while still picking up admin changes within
one minute.

Usage::

    from app.helpers.settings_reader import get_setting

    temperature = await get_setting(db, "chat_temperature", 0.7)
"""

import json
import logging
import time
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory cache: key -> (value, monotonic_timestamp)
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[Any, float]] = {}
_CACHE_TTL = 60.0  # seconds
_MISSING = object()  # sentinel for negative caching of absent keys


async def get_setting(db: AsyncSession, key: str, default: Any = None) -> Any:
    """Read a single system setting with 60-second in-memory cache.

    Args:
        db: Active async database session.
        key: The ``system_settings.key`` to look up.
        default: Value returned when the key does not exist in the DB.

    Returns:
        The stored value (auto-parsed from JSONB), or *default*.
    """
    now = time.monotonic()

    if key in _cache:
        value, cached_at = _cache[key]
        if now - cached_at < _CACHE_TTL:
            if value is _MISSING:
                return default
            return value

    try:
        result = await db.execute(
            text("SELECT value FROM system_settings WHERE key = :key"),
            {"key": key},
        )
        row = result.first()
    except Exception as exc:
        logger.warning("settings_reader: failed to read key=%r: %s", key, exc)
        return default

    if row is None:
        # Cache the miss so we don't hit the DB again for absent keys
        _cache[key] = (_MISSING, now)
        return default

    raw = row[0]

    # system_settings.value is JSONB so SQLAlchemy + asyncpg normally
    # returns a Python object already.  Handle the edge case where the
    # driver returns a raw JSON string.
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            value = raw
    else:
        value = raw

    _cache[key] = (value, now)
    return value


async def get_settings_batch(
    db: AsyncSession, keys: list[str], defaults: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Read multiple settings in a single query with caching.

    Args:
        db: Active async database session.
        keys: List of ``system_settings.key`` values to fetch.
        defaults: Optional mapping of key -> default value for missing keys.

    Returns:
        Dict mapping each requested key to its stored value (or its
        default if the key is absent from the DB).
    """
    defaults = defaults or {}
    now = time.monotonic()
    result: dict[str, Any] = {}
    uncached_keys: list[str] = []

    for key in keys:
        if key in _cache:
            value, cached_at = _cache[key]
            if now - cached_at < _CACHE_TTL:
                if value is not _MISSING:
                    result[key] = value
                # _MISSING means key absent -- skip to let defaults fill in
                continue
        uncached_keys.append(key)

    if uncached_keys:
        found_keys: set[str] = set()
        try:
            rows = await db.execute(
                text(
                    "SELECT key, value FROM system_settings " "WHERE key = ANY(:keys)"
                ),
                {"keys": uncached_keys},
            )
            for row in rows:
                raw = row[1]
                if isinstance(raw, str):
                    try:
                        value = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        value = raw
                else:
                    value = raw
                _cache[row[0]] = (value, now)
                result[row[0]] = value
                found_keys.add(row[0])
        except Exception as exc:
            logger.warning(
                "settings_reader: batch read failed for keys=%r: %s",
                uncached_keys,
                exc,
            )

        # Cache misses for keys not found in DB
        for key in uncached_keys:
            if key not in found_keys:
                _cache[key] = (_MISSING, now)

    # Fill in defaults for any keys not found in cache or DB
    for key in keys:
        if key not in result:
            result[key] = defaults.get(key)

    return result


def invalidate_cache(key: Optional[str] = None) -> None:
    """Clear the in-memory cache.

    Args:
        key: If provided, only that key is evicted.  If ``None``, the
            entire cache is cleared.
    """
    if key:
        _cache.pop(key, None)
    else:
        _cache.clear()
