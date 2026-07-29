import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_rls_db
from app.models.conversation import Conversation, ConversationTurn, Query
from app.models.organisation import User

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("/")
async def list_conversations(
    db: Session = Depends(get_rls_db),
    current_user: User = Depends(get_current_user),
):
    conversations = (
        db.query(Conversation)
        .filter(
            Conversation.user_id == current_user.id,
            Conversation.is_active == True,
        )
        .order_by(Conversation.updated_at.desc())
        .all()
    )

    return [
        {
            "id": str(conv.id),
            "title": conv.title,
            "status": conv.status,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
        }
        for conv in conversations
    ]


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_rls_db),
    current_user: User = Depends(get_current_user),
):
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "status": conversation.status,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }


@router.get("/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_rls_db),
    current_user: User = Depends(get_current_user),
):
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    turns = (
        db.query(ConversationTurn)
        .filter(ConversationTurn.conversation_id == conversation_id)
        .order_by(ConversationTurn.turn_index.asc())
        .all()
    )

    messages = []

    for turn in turns:
        message = {
            "id": str(turn.id),
            "role": turn.role,
            "content": turn.content,
            "turn_index": turn.turn_index,
            "is_summary": turn.is_summary,
            "created_at": turn.created_at.isoformat(),
        }

        if turn.role == "assistant" and turn.query_id:
            query = db.query(Query).filter(Query.id == turn.query_id).first()
            if query and query.citations:
                message["citations"] = query.citations

        messages.append(message)

    return {
        "conversation_id": str(conversation_id),
        "messages": messages,
    }


@router.delete("/{conversation_id}", status_code=204)
async def archive_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_rls_db),
    current_user: User = Depends(get_current_user),
):
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
            Conversation.is_active == True,
        )
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    conversation.is_active = False
    db.commit()
