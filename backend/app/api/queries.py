import datetime
import uuid
from typing import List, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.orchestrator_agent import orchestrate
from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.prompt_guard import validate_question
from app.models.conversation import Conversation
from app.models.organisation import User
from app.models.subscription import Subscription

router = APIRouter(prefix="/queries", tags=["queries"])

settings = get_settings()


class QueryRequest(BaseModel):
    question: str
    conversation_id: Optional[uuid.UUID] = None
    document_ids: Optional[List[str]] = None
    risk_types: Optional[List[str]] = None


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


async def check_usage_limits(user: User, db: Session) -> None:
    subscription = (
        db.query(Subscription).filter(Subscription.user_id == user.id).first()
    )

    if not subscription:
        return

    today = datetime.date.today()
    year_month = today.strftime("%Y-%m")

    redis = await aioredis.from_url(settings.REDIS_URL)
    queries_today_raw = await redis.get(f"queries:day:{user.id}:{today}")
    queries_month_raw = await redis.get(f"queries:month:{user.id}:{year_month}")
    await redis.aclose()

    queries_today = int(queries_today_raw) if queries_today_raw else 0
    queries_month = int(queries_month_raw) if queries_month_raw else 0

    if queries_today >= subscription.queries_per_day:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily query limit reached ({subscription.queries_per_day} queries). Resets tomorrow.",
        )

    if queries_month >= subscription.queries_per_month:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Monthly query limit reached ({subscription.queries_per_month} queries). Upgrade your plan for more.",
        )


async def increment_usage_counters(user_id: str) -> None:
    today = datetime.date.today()
    year_month = today.strftime("%Y-%m")

    redis = await aioredis.from_url(settings.REDIS_URL)
    await redis.incr(f"queries:day:{user_id}:{today}")
    await redis.incr(f"queries:month:{user_id}:{year_month}")
    # Daily counter expires after 24 hours - resets automatically each day
    await redis.expire(f"queries:day:{user_id}:{today}", 86400)
    await redis.aclose()


@router.post("/ask")
async def ask_question(
    request: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_question(request.question)

    # Check usage limits before processing - hard stop if limit reached
    await check_usage_limits(current_user, db)

    conversation = await get_or_create_conversation(
        conversation_id=request.conversation_id,
        user=current_user,
        db=db,
    )

    tier = await get_user_tier(current_user, db)

    # Increment counters after limit check passes - count this query
    await increment_usage_counters(str(current_user.id))

    result = await orchestrate(
        request=request.question,
        user_id=str(current_user.id),
        conversation_id=str(conversation.id),
        organisation_id=(
            str(current_user.organisation_id) if current_user.organisation_id else None
        ),
        tier=tier,
        document_ids=request.document_ids or [],
        db=db,
    )

    if result.get("requires_confirmation"):
        return {
            "requires_confirmation": True,
            "intent": result["intent"],
            "message": result["message"],
        }

    return {"status": "completed", "intent": result.get("intent")}
