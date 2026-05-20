import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.analytics import UserDailyStats
from app.models.audit import Notification
from app.models.organisation import User
from app.models.subscription import Subscription

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/")
async def get_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subscription = (
        db.query(Subscription).filter(Subscription.user_id == current_user.id).first()
    )

    if not subscription:
        return {
            "plan": "free",
            "queries_used_today": 0,
            "queries_limit_daily": 5,
            "queries_used_month": 0,
            "queries_limit_monthly": 100,
            "storage_used_mb": 0,
            "storage_limit_mb": 100,
        }

    today = datetime.date.today()
    year_month = today.strftime("%Y-%m")

    # Read real-time counts from Redis first
    import redis.asyncio as aioredis

    from app.core.config import get_settings

    settings = get_settings()

    redis = await aioredis.from_url(settings.REDIS_URL)

    queries_today_raw = await redis.get(f"queries:day:{current_user.id}:{today}")
    queries_month_raw = await redis.get(f"queries:month:{current_user.id}:{year_month}")

    await redis.aclose()

    queries_today = int(queries_today_raw) if queries_today_raw else 0
    queries_month = int(queries_month_raw) if queries_month_raw else 0

    # Fall back to database if Redis has no data
    if queries_today == 0:
        daily_stats = (
            db.query(UserDailyStats)
            .filter(
                UserDailyStats.user_id == current_user.id,
                UserDailyStats.date == today,
            )
            .first()
        )
        queries_today = daily_stats.queries_count if daily_stats else 0

    if queries_month == 0:
        from sqlalchemy import func

        monthly_total = (
            db.query(func.sum(UserDailyStats.queries_count))
            .filter(
                UserDailyStats.user_id == current_user.id,
                UserDailyStats.date >= datetime.date(today.year, today.month, 1),
            )
            .scalar()
            or 0
        )
        queries_month = int(monthly_total)

    return {
        "plan": subscription.plan,
        "queries_used_today": queries_today,
        "queries_limit_daily": subscription.queries_per_day,
        "queries_used_month": queries_month,
        "queries_limit_monthly": subscription.queries_per_month,
        "storage_limit_mb": subscription.storage_limit_mb,
    }


@router.get("/notifications")
async def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
        .order_by(Notification.created_at.desc())
        .limit(20)
        .all()
    )

    return [
        {
            "id": str(n.id),
            "type": n.type,
            "title": n.title,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        }
        for n in notifications
    ]


@router.patch("/notifications/{notification_id}/read", status_code=204)
async def mark_notification_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
        .first()
    )

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )

    notification.is_read = True
    db.commit()
