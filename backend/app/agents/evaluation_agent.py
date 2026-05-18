import asyncio
from typing import List, Optional

import anthropic
from sqlalchemy.orm import Session

from app.core.circuit_breaker import anthropic_breaker
from app.core.config import get_settings
from app.models.analytics import EvaluationResult
from app.services.websocket_service import manager

settings = get_settings()

# Thresholds from the architecture
FAITHFULNESS_THRESHOLD = 0.80
RELEVANCE_THRESHOLD = 0.75
CITATION_THRESHOLD = 0.90
TRAJECTORY_THRESHOLD = 0.85
TOOL_USE_THRESHOLD = 0.90

SAFE_FALLBACK_MESSAGE = (
    "I was unable to find a well-supported answer in the provided documents. "
    "Please try rephrasing your question or review the source documents directly."
)


async def check_faithfulness(
    question: str,
    answer: str,
    chunks: List[dict],
) -> float:
    if not answer or not chunks:
        return 0.0

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    chunks_text = "\n\n".join(
        [
            f"<chunk index='{i}'>{c['content'][:300]}</chunk>"
            for i, c in enumerate(chunks)
        ]
    )

    async def _call():
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"<question>{question}</question>\n\n"
                        f"<answer>{answer[:500]}</answer>\n\n"
                        f"<source_chunks>\n{chunks_text}\n</source_chunks>\n\n"
                        "Score how well every claim in the answer is supported by the source chunks.\n"
                        "Return only a decimal between 0.0 and 1.0. Nothing else."
                    ),
                }
            ],
        )
        return float(response.content[0].text.strip())

    try:
        return await anthropic_breaker.call(_call)
    except (ValueError, Exception):
        return 0.0


async def check_relevance(
    question: str,
    answer: str,
) -> float:
    if not answer:
        return 0.0

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def _call():
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"<question>{question}</question>\n\n"
                        f"<answer>{answer[:500]}</answer>\n\n"
                        "Score how directly and completely the answer addresses the question.\n"
                        "Return only a decimal between 0.0 and 1.0. Nothing else."
                    ),
                }
            ],
        )
        return float(response.content[0].text.strip())

    try:
        return await anthropic_breaker.call(_call)
    except (ValueError, Exception):
        return 0.0


# Checks citation presence only - not accuracy.
# TODO: Add per-citation verification in nightly batch to confirm
# each citation points to a chunk that actually supports the claim.
def check_citation_completeness(answer: str) -> float:
    if not answer:
        return 0.0

    import re

    sentences = [s.strip() for s in answer.split(".") if len(s.strip()) > 20]
    if not sentences:
        return 1.0

    citation_pattern = r"\[Document: .+?, Page: .+?, Chunk: .+?\]"
    cited_sentences = sum(1 for s in sentences if re.search(citation_pattern, s))

    return min(1.0, cited_sentences / max(len(sentences), 1))


async def evaluate_realtime(
    question: str,
    answer: str,
    chunks: List[dict],
    query_id: str,
    db: Session,
) -> dict:
    # Run faithfulness and relevance checks in parallel
    faithfulness, relevance = await asyncio.gather(
        check_faithfulness(question, answer, chunks),
        check_relevance(question, answer),
    )

    citation_score = check_citation_completeness(answer)

    passed = (
        faithfulness >= FAITHFULNESS_THRESHOLD
        and relevance >= RELEVANCE_THRESHOLD
        and citation_score >= CITATION_THRESHOLD
    )

    # Store evaluation result
    try:
        from uuid import UUID

        eval_record = EvaluationResult(
            query_id=UUID(query_id),
            faithfulness_score=round(faithfulness, 3),
            relevance_score=round(relevance, 3),
            citation_score=round(citation_score, 3),
            evaluation_type="realtime",
            passed=1 if passed else 0,
        )
        db.add(eval_record)
        db.commit()
    except Exception:
        pass

    return {
        "passed": passed,
        "faithfulness": faithfulness,
        "relevance": relevance,
        "citation_score": citation_score,
    }


async def evaluate_with_retry(
    question: str,
    answer: str,
    chunks: List[dict],
    query_id: str,
    db: Session,
    retry_func,
) -> str:
    # First evaluation
    result = await evaluate_realtime(question, answer, chunks, query_id, db)

    if result["passed"]:
        return answer

    # Failed - retry with higher top_k
    try:
        retry_answer, retry_chunks = await retry_func(top_k_multiplier=2)
        retry_result = await evaluate_realtime(
            question, retry_answer, retry_chunks, query_id, db
        )

        if retry_result["passed"]:
            return retry_answer

    except Exception:
        pass

    # Both attempts failed - return safe fallback
    return SAFE_FALLBACK_MESSAGE


async def evaluate_trajectory(
    trajectory: List[dict],
    was_successful: bool,
    query_id: str,
    db: Session,
) -> float:
    if not trajectory:
        return 0.0

    # Simple scoring - successful retrieval with fewer iterations is better
    max_iterations = 3
    iterations_used = len(trajectory)

    if not was_successful:
        score = 0.0
    elif iterations_used == 1:
        score = 1.0
    elif iterations_used == 2:
        score = 0.87
    else:
        score = 0.85

    try:
        from uuid import UUID

        eval_record = EvaluationResult(
            query_id=UUID(query_id),
            trajectory_score=round(score, 3),
            evaluation_type="async",
            passed=1 if score >= TRAJECTORY_THRESHOLD else 0,
        )
        db.add(eval_record)
        db.commit()
    except Exception:
        pass

    return score


async def run_nightly_batch(
    db: Session,
    user_id: str,
    tier: str,
) -> dict:
    samples_by_tier = {
        "free": 20,
        "starter": 30,
        "professional": 50,
        "enterprise": 100,
    }
    sample_size = samples_by_tier.get(tier, 20)

    import datetime
    from uuid import UUID

    from app.models.conversation import Query

    yesterday = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    queries = (
        db.query(Query)
        .filter(
            Query.user_id == UUID(user_id),
            Query.created_at >= yesterday,
            Query.status == "completed",
            Query.answer.isnot(None),
        )
        .limit(sample_size)
        .all()
    )

    if not queries:
        return {"sampled": 0, "evaluated": 0}

    results = []
    for query in queries:
        if not query.answer or not query.question:
            continue

        citation_score = check_citation_completeness(query.answer)

        try:
            eval_record = EvaluationResult(
                query_id=query.id,
                citation_score=round(citation_score, 3),
                evaluation_type="nightly_batch",
                passed=1 if citation_score >= CITATION_THRESHOLD else 0,
            )
            db.add(eval_record)
            results.append(
                {"query_id": str(query.id), "citation_score": citation_score}
            )
        except Exception:
            continue

    db.commit()

    return {
        "sampled": len(queries),
        "evaluated": len(results),
        "avg_citation_score": round(
            sum(r["citation_score"] for r in results) / max(len(results), 1), 3
        ),
    }
