from typing import List

from rank_bm25 import BM25Okapi


def tokenize(text: str) -> List[str]:
    # Simple whitespace and punctuation tokenization
    text = text.lower()
    for char in ".,;:!?()[]{}\"'\\/-":
        text = text.replace(char, " ")
    return [token for token in text.split() if token]


def bm25_search(
    query: str,
    chunks: List[dict],
    top_k: int,
) -> List[dict]:
    if not chunks:
        return []

    # Tokenize all chunk contents
    tokenized_chunks = [tokenize(chunk["content"]) for chunk in chunks]

    # Build BM25 index from chunks
    bm25 = BM25Okapi(tokenized_chunks)

    # Score the query against all chunks
    tokenized_query = tokenize(query)
    scores = bm25.get_scores(tokenized_query)

    # Attach scores to chunks and sort by score descending
    scored_chunks = []
    for i, chunk in enumerate(chunks):
        scored_chunks.append(
            {
                **chunk,
                "bm25_score": float(scores[i]),
            }
        )

    scored_chunks.sort(key=lambda x: x["bm25_score"], reverse=True)

    return scored_chunks[:top_k]
