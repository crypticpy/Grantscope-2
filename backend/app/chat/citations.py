"""Citation parser for chat assistant responses.

Extracts ``[N]`` reference markers from assistant response text and resolves
them against a source map built during RAG context assembly.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


def parse_citations(
    response_text: str,
    source_map: Dict[int, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Parse ``[N]`` citation references from the response text.

    Scans *response_text* for numeric bracket references and resolves each
    unique reference against the *source_map* produced during context
    retrieval.

    Args:
        response_text: The full assistant response containing ``[N]`` markers.
        source_map: A mapping from reference number to source metadata dict.
                    Each entry should contain at minimum ``title`` and ``url``.

    Returns:
        A list of citation dicts with keys ``index``, ``card_id``,
        ``card_slug``, ``source_id``, ``title``, ``url``, ``published_date``,
        and ``excerpt``.  Only citations whose reference number exists in
        *source_map* are included.
    """
    # Find all [N] references in the text
    citation_refs = re.findall(r"\[(\d+)\]", response_text)
    seen: set[int] = set()
    citations: List[Dict[str, Any]] = []

    for ref_str in citation_refs:
        ref_num = int(ref_str)
        if ref_num in seen:
            continue
        seen.add(ref_num)

        if source_info := source_map.get(ref_num):
            citations.append(
                {
                    "index": ref_num,
                    "card_id": source_info.get("card_id"),
                    "card_slug": source_info.get("card_slug", ""),
                    "source_id": source_info.get("source_id"),
                    "title": source_info.get("title", ""),
                    "url": source_info.get("url", ""),
                    "published_date": source_info.get("published_date"),
                    "excerpt": source_info.get("excerpt"),
                }
            )

    return citations
