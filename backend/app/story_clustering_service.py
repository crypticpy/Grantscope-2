"""
Story clustering service for Foresight.

Groups sources that report on the same underlying event or story using
semantic similarity of their vector embeddings. This enables two key
capabilities in the Source Quality Index (SQI):

1. **Corroboration counting** -- When multiple independent sources cover
   the same story, the SQI corroboration component increases, reflecting
   higher confidence in the information.

2. **Deduplication** -- The discovery queue can show one representative
   per cluster instead of N near-duplicate articles.

Algorithm
---------
The clustering uses a greedy union-find approach with cosine similarity:

1. Fetch sources and their VECTOR(1536) embeddings from the database.
2. Sources without embeddings are each assigned their own unique cluster
   (they cannot be compared, so we conservatively treat them as distinct).
3. For sources with embeddings, compute pairwise cosine similarity.
4. If similarity >= 0.90, merge the two sources into the same cluster
   using a union-find (disjoint set) data structure.
5. Assign a fresh UUID as story_cluster_id for each disjoint set.
6. Persist the story_cluster_id back to the sources table.

Threshold choice (0.90)
-----------------------
A threshold of 0.90 is deliberately high to avoid false merges. At this
level, only sources discussing the *same specific event* (e.g., two
articles about the same city council vote) are grouped together. Broader
topical overlap (e.g., two articles about housing policy in general) will
NOT be merged, which is the desired behavior -- we want corroboration of
the same story, not topical similarity.

For reference, the card deduplication threshold in the discovery pipeline
is 0.92 (see discovery_service.py). The story clustering threshold is
slightly lower because sources within a card are already topically
related, so we expect higher baseline similarity.

Usage
-----
    from app.story_clustering_service import (
        cluster_sources,
        get_cluster_count,
        cluster_new_sources,
    )

    # Cluster a batch of sources by their IDs
    result = cluster_sources(supabase, ["src-1", "src-2", "src-3"])
    # result = {
    #     "cluster_count": 2,
    #     "clusters": {"<uuid-a>": ["src-1", "src-2"], "<uuid-b>": ["src-3"]}
    # }

    # Count unique story clusters for a given card
    count = get_cluster_count(supabase, card_id="card-xyz")

    # Incrementally cluster new sources against a card's existing sources
    result = cluster_new_sources(supabase, card_id="card-xyz", new_source_ids=["src-4"])
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

import numpy as np
from supabase import Client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cosine similarity threshold for same-story clustering.
# Two sources with similarity >= this value are considered to cover the
# same underlying story or event.
# ---------------------------------------------------------------------------
SIMILARITY_THRESHOLD = 0.90


# ===========================================================================
# Union-Find (Disjoint Set) helper
# ===========================================================================


class _UnionFind:
    """
    Lightweight union-find / disjoint-set data structure.

    Used internally to merge sources into clusters as pairwise similarities
    are discovered.  Path compression and union-by-rank keep operations
    near O(alpha(n)) amortized.
    """

    def __init__(self, elements: List[str]) -> None:
        self._parent: Dict[str, str] = {e: e for e in elements}
        self._rank: Dict[str, int] = {e: 0 for e in elements}

    def find(self, x: str) -> str:
        """Find the root representative of *x* with path compression."""
        if self._parent[x] != x:
            self._parent[x] = self.find(self._parent[x])
        return self._parent[x]

    def union(self, x: str, y: str) -> None:
        """Merge the sets containing *x* and *y* (union by rank)."""
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        # Attach the shorter tree under the taller one.
        if self._rank[rx] < self._rank[ry]:
            self._parent[rx] = ry
        elif self._rank[rx] > self._rank[ry]:
            self._parent[ry] = rx
        else:
            self._parent[ry] = rx
            self._rank[rx] += 1

    def groups(self) -> Dict[str, List[str]]:
        """Return a mapping from root representative to member list."""
        clusters: Dict[str, List[str]] = {}
        for element in self._parent:
            root = self.find(element)
            clusters.setdefault(root, []).append(element)
        return clusters


# ===========================================================================
# Internal helpers
# ===========================================================================


def _cosine_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    """
    Compute the pairwise cosine similarity matrix for a set of embeddings.

    Parameters
    ----------
    embeddings : np.ndarray
        2-D array of shape (n_sources, embedding_dim).  Each row is a
        unit-normalised (or raw) embedding vector.

    Returns
    -------
    np.ndarray
        Symmetric (n_sources, n_sources) matrix of cosine similarities.
    """
    # Normalise each row to unit length to turn dot product into cosine sim.
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    # Guard against zero-length vectors (shouldn't happen with real
    # embeddings, but defensive coding avoids NaN propagation).
    norms = np.where(norms == 0, 1.0, norms)
    normed = embeddings / norms
    return normed @ normed.T


def _fetch_sources_with_embeddings(
    supabase: Client,
    source_ids: List[str],
) -> List[Dict[str, Any]]:
    """
    Fetch source rows including their embeddings from the ``sources`` table.

    Parameters
    ----------
    supabase : Client
        Authenticated Supabase client.
    source_ids : list[str]
        Source UUIDs to fetch.

    Returns
    -------
    list[dict]
        Each dict contains at minimum ``id`` and ``embedding`` (which may
        be ``None`` if the source was never embedded).
    """
    if not source_ids:
        return []

    # Supabase PostgREST `in_` filter accepts a CSV list.
    # Fetch in batches if the list is very large to avoid URL length limits.
    batch_size = 200
    results: List[Dict[str, Any]] = []
    for i in range(0, len(source_ids), batch_size):
        batch = source_ids[i : i + batch_size]
        resp = (
            supabase.table("sources")
            .select("id, card_id, embedding")
            .in_("id", batch)
            .execute()
        )
        results.extend(resp.data or [])
    return results


def _update_story_cluster_ids(
    supabase: Client,
    assignments: Dict[str, str],
) -> None:
    """
    Persist ``story_cluster_id`` assignments back to the sources table.

    Parameters
    ----------
    supabase : Client
        Authenticated Supabase client.
    assignments : dict[str, str]
        Mapping of source_id -> story_cluster_id (UUID string).
    """
    if not assignments:
        return

    # Update one row at a time.  Supabase PostgREST does not support
    # batch updates with varying values in a single call, and the
    # typical cluster count per card is small (< 50 sources).
    for source_id, cluster_id in assignments.items():
        try:
            supabase.table("sources").update({"story_cluster_id": cluster_id}).eq(
                "id", source_id
            ).execute()
        except Exception:
            logger.exception(
                "Failed to update story_cluster_id for source %s", source_id
            )


def _build_clusters(
    sources_with_emb: List[Dict[str, Any]],
    sources_without_emb: List[Dict[str, Any]],
) -> Dict[str, List[str]]:
    """
    Run the clustering algorithm and return cluster_id -> [source_ids].

    Parameters
    ----------
    sources_with_emb : list[dict]
        Source rows that have a non-None embedding.
    sources_without_emb : list[dict]
        Source rows that lack an embedding.

    Returns
    -------
    dict[str, list[str]]
        Mapping from generated cluster UUID to list of source IDs.
    """
    clusters: Dict[str, List[str]] = {}

    # --- Sources without embeddings: each is its own cluster. -----------
    # We cannot compare them semantically, so the conservative choice is
    # to treat each one as covering a unique story.
    for src in sources_without_emb:
        cid = str(uuid.uuid4())
        clusters[cid] = [src["id"]]

    # --- Sources with embeddings: pairwise cosine similarity. -----------
    if not sources_with_emb:
        return clusters

    # Single source with embedding -> trivially its own cluster.
    if len(sources_with_emb) == 1:
        cid = str(uuid.uuid4())
        clusters[cid] = [sources_with_emb[0]["id"]]
        return clusters

    ids = [s["id"] for s in sources_with_emb]
    embeddings = np.array([s["embedding"] for s in sources_with_emb], dtype=np.float64)

    sim_matrix = _cosine_similarity_matrix(embeddings)

    # Greedy union-find: merge any pair above the threshold.
    uf = _UnionFind(ids)
    n = len(ids)
    for i in range(n):
        for j in range(i + 1, n):
            if sim_matrix[i, j] >= SIMILARITY_THRESHOLD:
                uf.union(ids[i], ids[j])

    # Convert union-find groups to clusters with fresh UUIDs.
    for _root, members in uf.groups().items():
        cid = str(uuid.uuid4())
        clusters[cid] = members

    return clusters


# ===========================================================================
# Public API
# ===========================================================================


def cluster_sources(
    supabase_client: Client,
    source_ids: List[str],
) -> Dict[str, Any]:
    """
    Cluster a set of sources by semantic similarity and persist the results.

    This is the primary entry point for batch clustering.  It fetches the
    requested sources, groups them using cosine similarity on their
    embeddings, assigns ``story_cluster_id`` UUIDs, and writes the
    assignments back to the database.

    Parameters
    ----------
    supabase_client : Client
        Authenticated Supabase client.
    source_ids : list[str]
        IDs of sources to cluster.

    Returns
    -------
    dict
        ``cluster_count`` (int) -- number of distinct clusters.
        ``clusters`` (dict[str, list[str]]) -- cluster_id -> member source IDs.

    Edge cases
    ----------
    - Empty *source_ids*: returns ``{"cluster_count": 0, "clusters": {}}``.
    - Sources without embeddings are each placed in their own singleton
      cluster so they still contribute to the cluster count.
    """
    if not source_ids:
        logger.debug("cluster_sources called with empty source_ids list")
        return {"cluster_count": 0, "clusters": {}}

    logger.info("Clustering %d sources", len(source_ids))

    # 1. Fetch sources with embeddings.
    sources = _fetch_sources_with_embeddings(supabase_client, source_ids)

    if not sources:
        logger.warning(
            "No source rows found for provided IDs (count=%d)", len(source_ids)
        )
        return {"cluster_count": 0, "clusters": {}}

    # 2. Separate sources with and without embeddings.
    with_emb = [s for s in sources if s.get("embedding") is not None]
    without_emb = [s for s in sources if s.get("embedding") is None]

    if without_emb:
        logger.info(
            "%d / %d sources lack embeddings and will each form a singleton cluster",
            len(without_emb),
            len(sources),
        )

    # 3. Build clusters.
    clusters = _build_clusters(with_emb, without_emb)

    # 4. Persist story_cluster_id assignments.
    assignments: Dict[str, str] = {}
    for cluster_id, member_ids in clusters.items():
        for sid in member_ids:
            assignments[sid] = cluster_id

    _update_story_cluster_ids(supabase_client, assignments)

    logger.info(
        "Clustering complete: %d sources -> %d clusters",
        len(sources),
        len(clusters),
    )

    return {"cluster_count": len(clusters), "clusters": clusters}


def get_cluster_count(
    supabase_client: Client,
    card_id: str,
) -> int:
    """
    Count the number of unique story clusters for a given card.

    This is the value consumed by the SQI corroboration component.  A
    higher cluster count means more independent stories corroborate the
    card's topic.

    Parameters
    ----------
    supabase_client : Client
        Authenticated Supabase client.
    card_id : str
        The card whose sources should be inspected.

    Returns
    -------
    int
        Number of distinct ``story_cluster_id`` values among the card's
        sources.  Sources with NULL ``story_cluster_id`` (not yet
        clustered) are each counted as one cluster to avoid under-counting.
    """
    resp = (
        supabase_client.table("sources")
        .select("id, story_cluster_id")
        .eq("card_id", card_id)
        .execute()
    )
    rows = resp.data or []

    if not rows:
        return 0

    # Collect distinct non-NULL cluster IDs.
    cluster_ids = {
        r["story_cluster_id"] for r in rows if r.get("story_cluster_id") is not None
    }

    # Each source with NULL story_cluster_id is treated as its own
    # unique cluster because it hasn't been compared yet.  This avoids
    # artificially deflating the corroboration count before clustering
    # has run.
    unclustered_count = sum(1 for r in rows if r.get("story_cluster_id") is None)

    return len(cluster_ids) + unclustered_count


def cluster_new_sources(
    supabase_client: Client,
    card_id: str,
    new_source_ids: List[str],
) -> Dict[str, Any]:
    """
    Incrementally cluster newly added sources against a card's existing sources.

    When fresh sources are discovered for a card that already has clustered
    sources, this function re-clusters the *entire* set (existing + new) so
    that new sources can be merged into existing clusters if they are
    semantically similar.

    This avoids a common pitfall of incremental-only clustering where a new
    source that bridges two previously separate clusters would never cause
    those clusters to merge.

    Parameters
    ----------
    supabase_client : Client
        Authenticated Supabase client.
    card_id : str
        The card that owns the sources.
    new_source_ids : list[str]
        IDs of the newly added sources to integrate.

    Returns
    -------
    dict
        Same shape as :func:`cluster_sources`:
        ``cluster_count`` (int) and ``clusters`` (dict[str, list[str]]).

    Edge cases
    ----------
    - If *new_source_ids* is empty, returns the current cluster state for
      the card without re-clustering.
    - If the card has no existing sources, behaves identically to
      :func:`cluster_sources` on the new IDs alone.
    - Cross-card clustering is intentionally NOT performed.  Sources
      belonging to different cards are never merged into the same cluster.
      This keeps the corroboration count scoped to a single card's topic.
    """
    if not new_source_ids:
        logger.debug(
            "cluster_new_sources called with no new source IDs for card %s",
            card_id,
        )
        # Return current state without re-clustering.
        count = get_cluster_count(supabase_client, card_id)
        return {"cluster_count": count, "clusters": {}}

    # Fetch all existing source IDs for this card.
    existing_resp = (
        supabase_client.table("sources").select("id").eq("card_id", card_id).execute()
    )
    existing_ids = [r["id"] for r in (existing_resp.data or [])]

    # Combine existing + new, deduplicated, preserving order.
    seen: set = set()
    all_ids: List[str] = []
    for sid in existing_ids + new_source_ids:
        if sid not in seen:
            seen.add(sid)
            all_ids.append(sid)

    logger.info(
        "Re-clustering card %s: %d existing + %d new = %d total sources",
        card_id,
        len(existing_ids),
        len(new_source_ids),
        len(all_ids),
    )

    # Delegate to the full clustering function which handles fetch,
    # cluster, and persistence.
    return cluster_sources(supabase_client, all_ids)
