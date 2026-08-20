import uuid
from typing import AsyncGenerator, List

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.agent import AgentTrajectory
from app.models.conversation import Conversation, ConversationTurn, Query
from app.models.document import Document
from app.services.claude_service import extract_citations, generate_answer
from app.services.query_classifier import classify_query
from app.services.websocket_service import manager

settings = get_settings()


async def get_conversation_history(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    tier: str,
    db: Session,
) -> List[dict]:
    turns_by_tier = {
        "free": 5,
        "starter": 8,
        "professional": 10,
        "enterprise": 15,
    }
    max_turns = turns_by_tier.get(tier, 5)

    turns = (
        db.query(ConversationTurn)
        .filter(ConversationTurn.conversation_id == conversation_id)
        .order_by(ConversationTurn.turn_index.desc())
        .limit(max_turns)
        .all()
    )

    turns = list(reversed(turns))

    history = []
    for turn in turns:
        history.append(
            {
                "role": turn.role,
                "content": turn.content,
            }
        )

    return history


def get_chunk_metadata(chunk_ids: List[str], db: Session) -> dict:
    from app.models.processing import Chunk

    chunks = (
        db.query(Chunk)
        .filter(Chunk.id.in_([uuid.UUID(cid) for cid in chunk_ids]))
        .all()
    )

    return {
        str(chunk.id): {
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
        }
        for chunk in chunks
    }


def get_document_filenames(document_ids: List[str], db: Session) -> dict:
    documents = (
        db.query(Document)
        .filter(Document.id.in_([uuid.UUID(did) for did in document_ids]))
        .all()
    )

    return {str(doc.id): doc.filename for doc in documents}


async def process_query(
    question: str,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    organisation_id: uuid.UUID,
    tier: str,
    db: Session,
    document_ids: List[str] = None,
) -> AsyncGenerator[str, None]:
    # Step 1 - classify query
    query_type, top_k = await classify_query(question)

    # Steps 2-5 - retrieval agent handles complexity assessment,
    # embedding, semantic search, BM25, RRF, and iterative retrieval
    from app.agents.retrieval_agent import retrieve

    merged_chunks, trajectory, was_successful = await retrieve(
        question=question,
        query_type=query_type,
        user_id=str(user_id),
        organisation_id=str(organisation_id) if organisation_id else None,
        top_k=top_k,
        document_ids=document_ids,
    )

    # Step 6 - enrich chunks with metadata
    chunk_ids = [c["chunk_id"] for c in merged_chunks]
    document_id_list = list(set([c["document_id"] for c in merged_chunks]))

    chunk_metadata = get_chunk_metadata(chunk_ids, db)
    doc_filenames = get_document_filenames(document_id_list, db)

    for chunk in merged_chunks:
        meta = chunk_metadata.get(chunk["chunk_id"], {})
        chunk["page_number"] = meta.get("page_number")
        chunk["filename"] = doc_filenames.get(chunk["document_id"], "Unknown")

    # Step 7 - get conversation history
    history = await get_conversation_history(
        conversation_id=conversation_id,
        user_id=user_id,
        tier=tier,
        db=db,
    )

    # Step 8 - create query record
    query_record = Query(
        conversation_id=conversation_id,
        user_id=user_id,
        organisation_id=organisation_id,
        question=question,
        query_type=query_type.value,
        model_used="claude-haiku-4-5-20251001",
        status="processing",
        document_ids=[uuid.UUID(did) for did in document_id_list],
        chunks_used=[uuid.UUID(cid) for cid in chunk_ids],
    )
    db.add(query_record)
    db.commit()

    # Log agent trajectory - store both successful and failed paths
    # so we can calculate success rate in the evaluation framework
    trajectory_record = AgentTrajectory(
        query_id=query_record.id,
        user_id=user_id,
        agent_name="retrieval_agent",
        steps=trajectory,
        tools_used=["embed_single", "search_chunks", "bm25_search", "rrf_merge"],
        iterations=len(trajectory),
        was_successful=was_successful,
    )
    db.add(trajectory_record)
    db.commit()

    # Step 9 - stream answer from Claude
    full_answer = ""

    async for token in generate_answer(
        question=question,
        chunks=merged_chunks,
        query_type=query_type.value,
        conversation_history=history,
    ):
        full_answer += token
        await manager.send_to_user(
            user_id=str(user_id),
            message={
                "event": "query_token",
                "token": token,
                "query_id": str(query_record.id),
            },
        )
        yield token

    # Step 10 - extract citations and update query record
    citations = extract_citations(full_answer)

    query_record.answer = full_answer
    query_record.citations = citations
    query_record.status = "completed"
    db.commit()

    # Step 11 - store conversation turns
    turn_count = (
        db.query(ConversationTurn)
        .filter(ConversationTurn.conversation_id == conversation_id)
        .count()
    )

    db.add(
        ConversationTurn(
            conversation_id=conversation_id,
            query_id=query_record.id,
            role="user",
            content=question,
            turn_index=turn_count,
        )
    )

    db.add(
        ConversationTurn(
            conversation_id=conversation_id,
            query_id=query_record.id,
            role="assistant",
            content=full_answer,
            turn_index=turn_count + 1,
        )
    )

    db.commit()

    # Step 12 - notify completion via WebSocket
    await manager.send_to_user(
        user_id=str(user_id),
        message={
            "event": "query_complete",
            "query_id": str(query_record.id),
            "citations": citations,
        },
    )
