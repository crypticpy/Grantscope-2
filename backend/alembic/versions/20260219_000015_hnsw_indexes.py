"""Replace IVFFlat vector indexes with HNSW for better recall and latency.

IVFFlat indexes require periodic REINDEX and degrade on small tables.
HNSW provides consistently high recall without maintenance and handles
growing datasets gracefully.  The m and ef_construction parameters are
tuned for the expected corpus sizes (~10k–100k rows).

Revision ID: 0015_hnsw_indexes
Revises: 0014_ga_scope
Create Date: 2026-02-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0015_hnsw_indexes"
down_revision: Union[str, None] = "0014_ga_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop existing IVFFlat indexes
    op.execute("DROP INDEX IF EXISTS idx_cards_embedding")
    op.execute("DROP INDEX IF EXISTS idx_sources_embedding")
    op.execute("DROP INDEX IF EXISTS idx_discovery_blocks_embedding")
    op.execute("DROP INDEX IF EXISTS idx_discovered_sources_embedding")

    # Create HNSW indexes with cosine distance operator class
    op.execute(
        "CREATE INDEX idx_cards_embedding_hnsw "
        "ON cards USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 128)"
    )
    op.execute(
        "CREATE INDEX idx_sources_embedding_hnsw "
        "ON sources USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 128)"
    )
    op.execute(
        "CREATE INDEX idx_discovery_blocks_embedding_hnsw "
        "ON discovery_blocks USING hnsw (topic_embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    op.execute(
        "CREATE INDEX idx_discovered_sources_embedding_hnsw "
        "ON discovered_sources USING hnsw (content_embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 128)"
    )


def downgrade() -> None:
    # Drop HNSW indexes
    op.execute("DROP INDEX IF EXISTS idx_cards_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS idx_sources_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS idx_discovery_blocks_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS idx_discovered_sources_embedding_hnsw")

    # Recreate original IVFFlat indexes
    op.execute(
        "CREATE INDEX idx_cards_embedding "
        "ON cards USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )
    op.execute(
        "CREATE INDEX idx_sources_embedding "
        "ON sources USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )
    op.execute(
        "CREATE INDEX idx_discovery_blocks_embedding "
        "ON discovery_blocks USING ivfflat (topic_embedding vector_cosine_ops) "
        "WITH (lists = 50)"
    )
    op.execute(
        "CREATE INDEX idx_discovered_sources_embedding "
        "ON discovered_sources USING ivfflat (content_embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )
