import uuid
from typing import List, Tuple

import anthropic

from app.core.config import get_settings
from app.services.bm25_service import bm25_search
from app.services.embedding_service import embed_single
from app.services.qdrant_service import search_chunks
from app.services.query_classifier import QueryType
from app.services.rrf_service import reciprocal_rank_fusion

settings = get_settings()

MAX_ITERATIONS = 3
SUFFICIENCY_THRESHOLD = "sufficient"

COMPLEXITY_ASSESSMENT_PROMPT = """<question>{question}</question>

<task>Determine if this question requires searching multiple document sections or comparing information across sources to answer fully, versus a single direct lookup.</task>

<examples>
<example>
<question>What is the payment due date in this invoice?</question>
<answer>simple</answer>
</example>
<example>
<question>How does the liability clause in this contract compare to industry standard terms, and what related obligations does it create elsewhere in the document?</question>
<answer>complex</answer>
</example>
</examples>

Answer with exactly one word: simple or complex."""

SUFFICIENCY_EVALUATION_PROMPT = """<question>{question}</question>

<retrieved_chunks>
{chunk_summary}
</retrieved_chunks>

<task>Determine whether the retrieved chunks contain sufficient information to fully and accurately answer the question.</task>

<rules>
<rule id="1">Judge based on the full chunk content shown above, not just the first sentence.</rule>
<rule id="2">Mark insufficient if the chunks are on-topic but missing the specific detail the question asks for.</rule>
<rule id="3">Mark insufficient if the chunks appear to be about the wrong topic entirely.</rule>
<rule id="4">Only mark sufficient if the exact information needed to answer is present in the chunks, not merely related to it.</rule>
</rules>

Respond in this exact format:
STATUS: sufficient OR insufficient
MISSING: what specific information is missing, empty if sufficient"""

QUERY_OPTIMIZATION_PROMPT = """<original_question>{original_question}</original_question>

<missing_information>{missing_info}</missing_information>

<task>Write a refined search query that will retrieve the missing information.</task>

<rules>
<rule id="1">Preserve the core intent of the original question. Do not change what is being asked, only how it is phrased for search.</rule>
<rule id="2">Use different terminology than the original question if the missing information suggests the document uses different vocabulary for the concept.</rule>
<rule id="3">Be specific and targeted at the missing information, not a broader restatement of the original question.</rule>
</rules>

<example>
<original_question>What is the notice period for termination?</original_question>
<missing_information>The chunks discuss general contract duration but not specific notice requirements before ending the agreement.</missing_information>
<refined_query>written notice requirement before contract termination or expiry</refined_query>
</example>

Return only the search query, nothing else."""


async def assess_complexity(question: str, query_type: QueryType) -> bool:
    # Rule-based complexity assessment first
    simple_types = [QueryType.EXACT]
    if query_type in simple_types:
        return False  # Simple - no iteration needed

    complex_types = [QueryType.CROSS_DOC, QueryType.RISK]
    if query_type in complex_types:
        return True  # Complex - use iterative retrieval

    # For MIXED and CONCEPTUAL - use Haiku to assess
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=50,
        messages=[
            {
                "role": "user",
                "content": COMPLEXITY_ASSESSMENT_PROMPT.format(question=question),
            }
        ],
    )

    answer = response.content[0].text.strip().lower()
    return answer == "complex"


async def evaluate_sufficiency(
    question: str,
    chunks: List[dict],
    iteration: int,
) -> Tuple[str, str]:
    if not chunks:
        return "insufficient", "No relevant chunks were retrieved."

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    chunk_summary = "\n".join(
        [
            f"<chunk index='{i}'>{c['content'][:800]}</chunk>"
            for i, c in enumerate(chunks)
        ]
    )

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        messages=[
            {
                "role": "user",
                "content": SUFFICIENCY_EVALUATION_PROMPT.format(
                    question=question, chunk_summary=chunk_summary
                ),
            }
        ],
    )

    response_text = response.content[0].text.strip()
    lines = response_text.split("\n")

    status = "sufficient"
    missing = ""

    for line in lines:
        if line.startswith("STATUS:"):
            status = line.replace("STATUS:", "").strip().lower()
        elif line.startswith("MISSING:"):
            missing = line.replace("MISSING:", "").strip()

    return status, missing


async def optimize_query(original_question: str, missing_info: str) -> str:
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[
            {
                "role": "user",
                "content": QUERY_OPTIMIZATION_PROMPT.format(
                    original_question=original_question, missing_info=missing_info
                ),
            }
        ],
    )

    return response.content[0].text.strip()


async def iterative_retrieval(
    question: str,
    user_id: str,
    organisation_id: str,
    top_k: int,
    document_ids: List[str] = None,
) -> Tuple[List[dict], List[dict]]:
    all_chunks = []
    trajectory_steps = []

    current_query = question

    for iteration in range(MAX_ITERATIONS):
        step = {
            "iteration": iteration + 1,
            "query": current_query,
        }

        # Embed current query
        query_vector = await embed_single(current_query)

        # Semantic search
        semantic_results = search_chunks(
            query_vector=query_vector,
            user_id=user_id,
            organisation_id=organisation_id,
            top_k=top_k,
            document_ids=document_ids,
        )

        # BM25 search on semantic candidates
        bm25_results = bm25_search(
            query=current_query,
            chunks=semantic_results,
            top_k=top_k,
        )

        # Merge with RRF
        iteration_chunks = reciprocal_rank_fusion(
            bm25_results=bm25_results,
            semantic_results=semantic_results,
            top_k=top_k,
        )

        step["chunks_retrieved"] = len(iteration_chunks)

        # Merge with previous iterations - deduplicate by chunk_id
        existing_ids = {c["chunk_id"] for c in all_chunks}
        new_chunks = [c for c in iteration_chunks if c["chunk_id"] not in existing_ids]
        all_chunks.extend(new_chunks)

        step["new_chunks_added"] = len(new_chunks)

        # Evaluate sufficiency
        status, missing = await evaluate_sufficiency(question, all_chunks, iteration)
        step["sufficiency_status"] = status
        step["missing_info"] = missing

        trajectory_steps.append(step)

        if status == SUFFICIENCY_THRESHOLD:
            break

        if iteration < MAX_ITERATIONS - 1:
            # Optimize query for next iteration
            current_query = await optimize_query(question, missing)
            step["next_query"] = current_query

    return all_chunks, trajectory_steps


async def retrieve(
    question: str,
    query_type: QueryType,
    user_id: str,
    organisation_id: str,
    top_k: int,
    document_ids: List[str] = None,
) -> Tuple[List[dict], List[dict], bool]:
    is_complex = await assess_complexity(question, query_type)

    if not is_complex:
        # Simple path - single retrieval
        query_vector = await embed_single(question)

        semantic_results = search_chunks(
            query_vector=query_vector,
            user_id=user_id,
            organisation_id=organisation_id,
            top_k=top_k,
            document_ids=document_ids,
        )

        bm25_results = bm25_search(
            query=question,
            chunks=semantic_results,
            top_k=top_k,
        )

        chunks = reciprocal_rank_fusion(
            bm25_results=bm25_results,
            semantic_results=semantic_results,
            top_k=top_k,
        )

        trajectory = [
            {"iteration": 1, "query": question, "chunks_retrieved": len(chunks)}
        ]
        return chunks, trajectory, True

    # Complex path - iterative retrieval
    chunks, trajectory = await iterative_retrieval(
        question=question,
        user_id=user_id,
        organisation_id=organisation_id,
        top_k=top_k,
        document_ids=document_ids,
    )

    was_successful = len(chunks) > 0
    return chunks, trajectory, was_successful
