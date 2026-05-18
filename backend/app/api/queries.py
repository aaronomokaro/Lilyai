import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.conversation import Conversation
from app.models.organisation import User
from app.models.subscription import Subscription
from app.services.query_service import process_query

router = APIRouter(prefix="/queries", tags=["queries"])


class QueryRequest(BaseModel):
    question: str
    conversation_id: Optional[uuid.UUID] = None
    document_ids: Optional[List[str]] = None


async def get_or_create_conversation(
    conversation_id: Optional[uuid.UUID],
    user: User,
    db: Session,
) -> Conversation:
    if conversation_id:
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id,
            )
            .first()
        )

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )
        return conversation

    # Create new conversation
    conversation = Conversation(
        user_id=user.id,
        organisation_id=user.organisation_id,
        status="active",
    )
    db.add(conversation)
    db.commit()
    return conversation


async def get_user_tier(user: User, db: Session) -> str:
    subscription = (
        db.query(Subscription).filter(Subscription.user_id == user.id).first()
    )

    if not subscription:
        return "free"

    return subscription.plan


@router.post("/ask")
async def ask_question(
    request: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not request.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty.",
        )

    if len(request.question) > 2000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question too long. Maximum 2000 characters.",
        )

    conversation = await get_or_create_conversation(
        conversation_id=request.conversation_id,
        user=current_user,
        db=db,
    )

    tier = await get_user_tier(current_user, db)

    async def stream_response():
        async for token in process_query(
            question=request.question,
            conversation_id=conversation.id,
            user_id=current_user.id,
            organisation_id=current_user.organisation_id,
            tier=tier,
            db=db,
            document_ids=request.document_ids,
        ):
            yield token

    return StreamingResponse(
        stream_response(),
        media_type="text/plain",
    )
