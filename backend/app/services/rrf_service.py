from typing import List

RRF_K = 60


def reciprocal_rank_fusion(
    bm25_results: List[dict],
    semantic_results: List[dict],
    top_k: int,
) -> List[dict]:
    scores = {}

    # Score BM25 results by rank position
    for rank, chunk in enumerate(bm25_results):
        chunk_id = chunk["chunk_id"]
        if chunk_id not in scores:
            scores[chunk_id] = {"chunk": chunk, "score": 0.0}
        scores[chunk_id]["score"] += 1 / (RRF_K + rank + 1)

    # Score semantic results by rank position
    for rank, chunk in enumerate(semantic_results):
        chunk_id = chunk["chunk_id"]
        if chunk_id not in scores:
            scores[chunk_id] = {"chunk": chunk, "score": 0.0}
        scores[chunk_id]["score"] += 1 / (RRF_K + rank + 1)

    # Sort by combined RRF score descending
    sorted_chunks = sorted(
        scores.values(),
        key=lambda x: x["score"],
        reverse=True,
    )

    return [item["chunk"] for item in sorted_chunks[:top_k]]
