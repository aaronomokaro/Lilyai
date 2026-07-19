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

FAITHFULNESS_PROMPT = """<question>{question}</question>

<answer>{answer}</answer>

<source_chunks>
{chunks_text}
</source_chunks>

<task>Score how well every claim in the answer is supported by the source chunks.</task>

<rules>
<rule id="1">A claim is supported if it is directly stated or closely and accurately paraphrased in the source chunks.</rule>
<rule id="2">A claim combining information from two or more chunks is supported only if each part of the combination is individually present in the chunks.</rule>
<rule id="3">A claim that goes beyond what the chunks state, even if plausible, is not supported.</rule>
<rule id="4">Score 1.0 only if every claim in the answer is fully supported. Score proportionally lower for each unsupported or partially supported claim.</rule>
<rule id="5">If the answer correctly states no information was found, score 1.0.</rule>
</rules>

Return only a decimal between 0.0 and 1.0. Nothing else."""

RELEVANCE_PROMPT = """<question>{question}</question>

<answer>{answer}</answer>

<task>Score how directly and completely the answer addresses the question.</task>

<rules>
<rule id="1">Score 1.0 if the answer fully addresses every part of the question.</rule>
<rule id="2">Score lower if the answer addresses only part of a multi-part question.</rule>
<rule id="3">Score lower if the answer includes information not relevant to what was asked, even if accurate.</rule>
<rule id="4">If the answer correctly states no information was found and the question genuinely cannot be answered from documents, score 1.0.</rule>
</rules>

Return only a decimal between 0.0 and 1.0. Nothing else."""

TRAJECTORY_EVALUATION_PROMPT = """<original_question>{original_question}</original_question>

<retrieval_trajectory>
{trajectory_text}
</retrieval_trajectory>

<was_successful>{was_successful}</was_successful>

<task>Score the quality of the retrieval reasoning process shown above, not the final answer itself.</task>

<rules>
<rule id="1">A trajectory that reaches sufficiency in fewer iterations because the query was well-targeted from the start scores higher than one that needed multiple attempts due to poor initial query construction.</rule>
<rule id="2">A trajectory where each query rewrite in "next_query" shows clear, logical improvement based on the stated missing information scores higher than one where rewrites are vague or repeat the same approach.</rule>
<rule id="3">A trajectory that reached sufficiency by coincidence rather than through a logical search path should score lower, even if it happened to reach sufficiency in one iteration.</rule>
<rule id="4">If was_successful is false, score no higher than 0.3 regardless of how many iterations were attempted.</rule>
<rule id="5">Score 1.0 only for a trajectory with no wasted iterations and clearly logical query construction throughout.</rule>
</rules>

Return only a decimal between 0.0 and 1.0. Nothing else."""


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
            f"<chunk index='{i}'>{c['content'][:1200]}</chunk>"
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
                    "content": FAITHFULNESS_PROMPT.format(
                        question=question,
                        answer=answer[:2000],
                        chunks_text=chunks_text,
                    ),
                }
            ],
        )
        return float(response.content[0].text.strip())

    try:
        return await anthropic_breaker.call(_call)
    except Exception:
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
                    "content": RELEVANCE_PROMPT.format(
                        question=question, answer=answer[:2000]
                    ),
                }
            ],
        )
        return float(response.content[0].text.strip())

    try:
        return await anthropic_breaker.call(_call)
    except Exception:
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
    except Exception as e:
        import logging

        logging.getLogger(__name__).error(
            f"Failed to store realtime evaluation result for query {query_id}: {e}"
        )

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

    original_question = trajectory[0].get("query", "")

    trajectory_text = "\n\n".join(
        [
            f"<step iteration='{step.get('iteration')}'>\n"
            f"<query>{step.get('query', '')}</query>\n"
            f"<chunks_retrieved>{step.get('chunks_retrieved', 0)}</chunks_retrieved>\n"
            f"<sufficiency_status>{step.get('sufficiency_status', 'unknown')}</sufficiency_status>\n"
            f"<missing_info>{step.get('missing_info', '')}</missing_info>\n"
            f"<next_query>{step.get('next_query', 'n/a - final iteration')}</next_query>\n"
            f"</step>"
            for step in trajectory
        ]
    )

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def _call():
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            messages=[
                {
                    "role": "user",
                    "content": TRAJECTORY_EVALUATION_PROMPT.format(
                        original_question=original_question,
                        trajectory_text=trajectory_text,
                        was_successful=was_successful,
                    ),
                }
            ],
        )
        return float(response.content[0].text.strip())

    try:
        score = await anthropic_breaker.call(_call)
    except Exception:
        score = 0.0

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
