import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_nightly_evaluation():
    logger.info("Starting nightly evaluation batch job")
    try:
        from sqlalchemy import text

        from app.agents.evaluation_agent import run_nightly_batch
        from app.core.database import SessionLocal, set_rls_context
        from app.models.organisation import User
        from app.models.subscription import Subscription

        db = SessionLocal()
        try:
            users = (
                db.query(User)
                .from_statement(
                    text("SELECT * FROM get_active_users_for_maintenance()")
                )
                .all()
            )
            for user in users:
                set_rls_context(db, user_id=str(user.id))
                subscription = (
                    db.query(Subscription)
                    .filter(Subscription.user_id == user.id)
                    .first()
                )
                tier = subscription.plan if subscription else "free"
                await run_nightly_batch(
                    db=db,
                    user_id=str(user.id),
                    tier=tier,
                )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Nightly evaluation batch failed: {e}")


async def run_usage_aggregation():
    logger.info("Starting nightly usage aggregation job")
    try:
        import datetime

        import redis.asyncio as aioredis
        from sqlalchemy import text

        from app.core.config import get_settings
        from app.core.database import SessionLocal, set_rls_context
        from app.models.analytics import UserDailyStats
        from app.models.organisation import User

        settings = get_settings()
        db = SessionLocal()

        try:
            yesterday = datetime.date.today() - datetime.timedelta(days=1)
            users = (
                db.query(User)
                .from_statement(
                    text("SELECT * FROM get_active_users_for_maintenance()")
                )
                .all()
            )

            redis = await aioredis.from_url(settings.REDIS_URL)

            for user in users:
                set_rls_context(db, user_id=str(user.id))
                date_key = yesterday.strftime("%Y-%m-%d")
                queries_raw = await redis.get(f"queries:day:{user.id}:{date_key}")
                queries_count = int(queries_raw) if queries_raw else 0

                if queries_count > 0:
                    existing = (
                        db.query(UserDailyStats)
                        .filter(
                            UserDailyStats.user_id == user.id,
                            UserDailyStats.date == yesterday,
                        )
                        .first()
                    )

                    if existing:
                        existing.queries_count = queries_count
                    else:
                        db.add(
                            UserDailyStats(
                                user_id=user.id,
                                date=yesterday,
                                queries_count=queries_count,
                            )
                        )

            await redis.aclose()
            db.commit()

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Usage aggregation failed: {e}")


async def run_qdrant_keepalive():
    logger.info("Starting Qdrant keepalive ping")
    try:
        from app.services.qdrant_service import get_qdrant_client

        client = get_qdrant_client()
        collections = client.get_collections()
        logger.info(
            f"Qdrant keepalive successful. Collections: {[c.name for c in collections.collections]}"
        )
    except Exception as e:
        logger.error(f"Qdrant keepalive failed: {e}")


async def run_output_cleanup():
    logger.info("Starting nightly output cleanup job")
    try:
        import datetime

        from sqlalchemy import text

        from app.core.database import SessionLocal, set_rls_context
        from app.models.organisation import User
        from app.models.output import Output
        from app.services.s3_service import delete_document

        db = SessionLocal()
        now = datetime.datetime.utcnow()

        try:
            users = (
                db.query(User)
                .from_statement(
                    text("SELECT * FROM get_active_users_for_maintenance()")
                )
                .all()
            )

            total_cleaned = 0
            for user in users:
                set_rls_context(db, user_id=str(user.id))
                expired_outputs = (
                    db.query(Output)
                    .filter(
                        Output.is_permanent == False,
                        Output.expires_at <= now,
                        Output.status == "ready",
                    )
                    .all()
                )

                for output in expired_outputs:
                    try:
                        await delete_document(output.s3_key)
                    except Exception:
                        pass
                    output.status = "expired"
                total_cleaned += len(expired_outputs)

            db.commit()
            logger.info(f"Cleaned up {total_cleaned} expired outputs")

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Output cleanup failed: {e}")


def setup_scheduler():
    # Nightly evaluation batch - 2am every day
    scheduler.add_job(
        run_nightly_evaluation,
        CronTrigger(hour=2, minute=0),
        id="nightly_evaluation",
        replace_existing=True,
    )

    # Usage aggregation - 2:15am every day
    # Runs after evaluation to ensure query counts are stable
    scheduler.add_job(
        run_usage_aggregation,
        CronTrigger(hour=2, minute=15),
        id="usage_aggregation",
        replace_existing=True,
    )

    # Output cleanup - 2:30am every day
    scheduler.add_job(
        run_output_cleanup,
        CronTrigger(hour=2, minute=30),
        id="output_cleanup",
        replace_existing=True,
    )

    scheduler.add_job(
        run_qdrant_keepalive,
        CronTrigger(hour=6, minute=0),
        id="qdrant_keepalive",
        replace_existing=True,
    )

    return scheduler
