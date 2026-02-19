"""System monitoring admin endpoints -- health checks, DB stats, version info."""

import logging
import os
import sys
import time

import fastapi
import sqlalchemy
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.admin_deps import require_admin
from app.database import engine
from app.deps import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# GET /admin/monitoring/health
# ---------------------------------------------------------------------------
@router.get("/admin/monitoring/health")
async def system_health(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """System health overview: DB latency, table counts, worker queue, embeddings, description quality."""
    try:
        # -- Database latency -----------------------------------------------
        t0 = time.time()
        await db.execute(text("SELECT 1"))
        db_latency_ms = round((time.time() - t0) * 1000, 2)

        # -- Table counts (single query for efficiency) ---------------------
        counts_sql = text(
            """
            SELECT
                (SELECT count(*) FROM cards)                                       AS cards,
                (SELECT count(*) FROM cards WHERE status = 'active')               AS cards_active,
                (SELECT count(*) FROM sources)                                     AS sources,
                (SELECT count(*) FROM users)                                       AS users,
                (SELECT count(*) FROM research_tasks)                              AS research_tasks,
                (SELECT count(*) FROM discovery_runs)                              AS discovery_runs,
                (SELECT count(*) FROM workstreams)                                 AS workstreams
        """
        )
        row = (await db.execute(counts_sql)).one()
        counts = {
            "cards": row.cards,
            "cards_active": row.cards_active,
            "sources": row.sources,
            "users": row.users,
            "research_tasks": row.research_tasks,
            "discovery_runs": row.discovery_runs,
            "workstreams": row.workstreams,
        }

        # -- Worker queue depth ---------------------------------------------
        worker_sql = text(
            """
            SELECT
                count(*) FILTER (WHERE status = 'queued')      AS queued,
                count(*) FILTER (WHERE status = 'processing')  AS processing,
                count(*) FILTER (WHERE status = 'completed'
                                   AND completed_at >= now() - interval '24 hours')
                                                                AS completed_24h,
                count(*) FILTER (WHERE status = 'failed'
                                   AND completed_at >= now() - interval '24 hours')
                                                                AS failed_24h
            FROM research_tasks
        """
        )
        wrow = (await db.execute(worker_sql)).one()

        last_completed_sql = text(
            """
            SELECT completed_at
            FROM research_tasks
            WHERE status = 'completed' AND completed_at IS NOT NULL
            ORDER BY completed_at DESC
            LIMIT 1
        """
        )
        lc_result = (await db.execute(last_completed_sql)).scalar_one_or_none()

        worker = {
            "queue_depth": {
                "queued": wrow.queued,
                "processing": wrow.processing,
                "completed_24h": wrow.completed_24h,
                "failed_24h": wrow.failed_24h,
            },
            "last_completed": lc_result.isoformat() if lc_result else None,
        }

        # -- Embedding coverage ---------------------------------------------
        emb_sql = text(
            """
            SELECT
                count(*) FILTER (WHERE embedding IS NOT NULL) AS with_embedding,
                count(*) FILTER (WHERE embedding IS NULL)     AS without_embedding,
                count(*)                                       AS total
            FROM cards
        """
        )
        erow = (await db.execute(emb_sql)).one()
        coverage_pct = round(
            (erow.with_embedding / erow.total * 100) if erow.total > 0 else 0.0, 2
        )
        embeddings = {
            "cards_with_embedding": erow.with_embedding,
            "cards_without_embedding": erow.without_embedding,
            "coverage_pct": coverage_pct,
        }

        # -- Description quality buckets ------------------------------------
        desc_sql = text(
            """
            SELECT
                count(*) FILTER (WHERE description IS NULL OR description = '')           AS missing,
                count(*) FILTER (WHERE description IS NOT NULL AND description != ''
                                   AND length(description) < 400)                          AS thin,
                count(*) FILTER (WHERE length(description) >= 400
                                   AND length(description) < 1600)                         AS short,
                count(*) FILTER (WHERE length(description) >= 1600
                                   AND length(description) < 3200)                         AS adequate,
                count(*) FILTER (WHERE length(description) >= 3200)                        AS comprehensive
            FROM cards
        """
        )
        drow = (await db.execute(desc_sql)).one()
        descriptions = {
            "missing": drow.missing,
            "thin": drow.thin,
            "short": drow.short,
            "adequate": drow.adequate,
            "comprehensive": drow.comprehensive,
        }

        return {
            "database": {"status": "ok", "latency_ms": db_latency_ms},
            "counts": counts,
            "worker": worker,
            "embeddings": embeddings,
            "descriptions": descriptions,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Health check failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {type(e).__name__}",
        ) from e


# ---------------------------------------------------------------------------
# GET /admin/monitoring/db-stats
# ---------------------------------------------------------------------------

_TRACKED_TABLES = [
    "cards",
    "sources",
    "users",
    "research_tasks",
    "discovery_runs",
    "workstreams",
    "rss_feeds",
    "system_settings",
]


@router.get("/admin/monitoring/db-stats")
async def db_stats(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """Database statistics: per-table sizes, total DB size, connection pool info."""
    try:
        tables = []
        for table_name in _TRACKED_TABLES:
            row_sql = text("SELECT count(*) AS cnt FROM " + table_name)  # noqa: S608
            try:
                cnt = (await db.execute(row_sql)).scalar_one()
            except Exception:
                # Table might not exist yet — rollback aborted transaction
                await db.rollback()
                cnt = 0

            size_sql = text(
                """
                SELECT
                    pg_size_pretty(pg_total_relation_size(:tbl))  AS total_size,
                    pg_size_pretty(pg_indexes_size(:tbl))         AS index_size
            """
            )
            try:
                srow = (await db.execute(size_sql, {"tbl": table_name})).one()
                total_size = srow.total_size
                index_size = srow.index_size
            except Exception:
                await db.rollback()
                total_size = "N/A"
                index_size = "N/A"

            tables.append(
                {
                    "name": table_name,
                    "row_count": cnt,
                    "total_size": total_size,
                    "index_size": index_size,
                }
            )

        # Total database size
        db_size_sql = text(
            "SELECT pg_size_pretty(pg_database_size(current_database())) AS db_size"
        )
        total_db_size = (await db.execute(db_size_sql)).scalar_one()

        # Connection pool stats
        pool_info: dict
        if engine is not None:
            pool = engine.pool
            pool_info = {
                "size": pool.size(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
            }
        else:
            pool_info = {"size": 0, "checked_out": 0, "overflow": 0}

        return {
            "tables": tables,
            "total_size": total_db_size,
            "connection_pool": pool_info,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("DB stats retrieval failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"DB stats retrieval failed: {type(e).__name__}",
        ) from e


# ---------------------------------------------------------------------------
# GET /admin/monitoring/version
# ---------------------------------------------------------------------------
@router.get("/admin/monitoring/version")
async def version_info(
    _current_user: dict = Depends(require_admin),
):
    """Build and runtime version information."""
    return {
        "version": os.getenv("BUILD_VERSION", "dev"),
        "build_date": os.getenv("BUILD_DATE", "unknown"),
        "git_sha": os.getenv("GIT_SHA", "unknown"),
        "python_version": sys.version,
        "fastapi_version": fastapi.__version__,
        "sqlalchemy_version": sqlalchemy.__version__,
        "environment": os.getenv("ENVIRONMENT", "development"),
    }
