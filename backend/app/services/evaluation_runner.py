import asyncio
import logging
from typing import List

from sqlalchemy.orm import Session

from app.agents.evaluation_agent import (
    CITATION_THRESHOLD,
    FAITHFULNESS_THRESHOLD,
    RELEVANCE_THRESHOLD,
    check_citation_completeness,
    check_faithfulness,
    check_relevance,
)
from app.services.ground_truth import TestCase, dataset

logger = logging.getLogger(__name__)

# Passing thresholds from the architecture
CORRECTNESS_THRESHOLD = 0.90
COMPLETENESS_THRESHOLD = 0.80
NO_ANSWER_THRESHOLD = 0.95


async def score_answer(
    test_case: TestCase,
    actual_answer: str,
    retrieved_chunks: List[dict],
) -> dict:
    faithfulness, relevance = await asyncio.gather(
        check_faithfulness(test_case.question, actual_answer, retrieved_chunks),
        check_relevance(test_case.question, actual_answer),
    )

    citation_score = check_citation_completeness(actual_answer)

    # No-answer cases are special - hallucinating an answer is a critical failure
    if test_case.is_no_answer:
        safe_fallback = "I could not find this information in the provided documents"
        no_answer_correct = safe_fallback.lower() in actual_answer.lower()
        no_answer_score = 1.0 if no_answer_correct else 0.0
    else:
        no_answer_score = None

    passed = faithfulness >= FAITHFULNESS_THRESHOLD and relevance >= RELEVANCE_THRESHOLD

    if test_case.is_no_answer:
        passed = passed and no_answer_score == 1.0

    return {
        "test_case_id": test_case.id,
        "query_type": test_case.query_type,
        "capability": test_case.capability,
        "is_no_answer": test_case.is_no_answer,
        "faithfulness": round(faithfulness, 3),
        "relevance": round(relevance, 3),
        "citation_score": round(citation_score, 3),
        "no_answer_score": no_answer_score,
        "passed": passed,
    }


async def run_evaluation(
    user_id: str,
    organisation_id: str,
    db: Session,
    sample_size: int = None,
) -> dict:
    if sample_size:
        test_cases = dataset.get_sample(sample_size)
    else:
        test_cases = dataset.test_cases

    if not test_cases:
        return {
            "error": "No test cases found. Check ground_truth.json exists in backend/data/",
            "total": 0,
        }

    results = []
    passed_count = 0
    failed_cases = []

    for test_case in test_cases:
        try:
            from app.agents.retrieval_agent import retrieve
            from app.services.query_classifier import QueryType

            query_type_map = {
                "exact": QueryType.EXACT,
                "conceptual": QueryType.CONCEPTUAL,
                "mixed": QueryType.MIXED,
                "cross_doc": QueryType.CROSS_DOC,
                "risk": QueryType.RISK,
            }

            query_type = query_type_map.get(test_case.query_type, QueryType.MIXED)

            chunks, _, _ = await retrieve(
                question=test_case.question,
                query_type=query_type,
                user_id=user_id,
                organisation_id=organisation_id,
                top_k=5,
                document_ids=None,
            )

            from app.services.claude_service import generate_answer

            full_answer = ""
            async for token in generate_answer(
                question=test_case.question,
                chunks=chunks,
                query_type=test_case.query_type,
            ):
                full_answer += token

            result = await score_answer(test_case, full_answer, chunks)
            results.append(result)

            if result["passed"]:
                passed_count += 1
            else:
                failed_cases.append(
                    {
                        "test_case_id": test_case.id,
                        "question": test_case.question,
                        "faithfulness": result["faithfulness"],
                        "relevance": result["relevance"],
                        "citation_score": result["citation_score"],
                    }
                )

        except Exception as e:
            logger.error(f"Test case {test_case.id} failed with error: {e}")
            results.append(
                {
                    "test_case_id": test_case.id,
                    "error": str(e),
                    "passed": False,
                }
            )

    total = len(test_cases)
    pass_rate = round(passed_count / total, 3) if total > 0 else 0

    avg_faithfulness = round(
        sum(r.get("faithfulness", 0) for r in results) / max(total, 1), 3
    )
    avg_relevance = round(
        sum(r.get("relevance", 0) for r in results) / max(total, 1), 3
    )
    avg_citation = round(
        sum(r.get("citation_score", 0) for r in results) / max(total, 1), 3
    )

    no_answer_cases = [r for r in results if r.get("is_no_answer")]
    no_answer_pass_rate = round(
        sum(1 for r in no_answer_cases if r.get("no_answer_score") == 1.0)
        / max(len(no_answer_cases), 1),
        3,
    )

    return {
        "total": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "pass_rate": pass_rate,
        "avg_faithfulness": avg_faithfulness,
        "avg_relevance": avg_relevance,
        "avg_citation_score": avg_citation,
        "no_answer_pass_rate": no_answer_pass_rate,
        "failed_cases": failed_cases,
        "thresholds": {
            "faithfulness": FAITHFULNESS_THRESHOLD,
            "relevance": RELEVANCE_THRESHOLD,
            "citation": CITATION_THRESHOLD,
            "no_answer": NO_ANSWER_THRESHOLD,
        },
    }
