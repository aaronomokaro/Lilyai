import json
from typing import Optional
from fastapi import Request, Response, HTTPException, status
import redis.asyncio as aioredis
from app.core.config import get_settings

settings = get_settings()

IDEMPOTENCY_TTL = 86400  # 24 hours in seconds


async def get_redis() -> aioredis.Redis:
    return await aioredis.from_url(settings.REDIS_URL)


def idempotency_key_for(prefix: str, user_id: str, key: str) -> str:
    return f"idempotency:{prefix}:{user_id}:{key}"


async def get_cached_response(redis_key: str) -> Optional[dict]:
    redis = await get_redis()
    data = await redis.get(redis_key)
    await redis.aclose()
    if data:
        return json.loads(data)
    return None


async def store_response(redis_key: str, response_data: dict) -> None:
    redis = await get_redis()
    await redis.set(redis_key, json.dumps(response_data), ex=IDEMPOTENCY_TTL)
    await redis.aclose()


def get_idempotency_key(request: Request) -> Optional[str]:
    return request.headers.get("Idempotency-Key")


async def check_idempotency(
    prefix: str,
    user_id: str,
    request: Request,
) -> Optional[dict]:
    key = get_idempotency_key(request)

    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required for this operation",
        )

    redis_key = idempotency_key_for(prefix, user_id, key)
    cached = await get_cached_response(redis_key)

    if cached:
        return cached

    return None


async def save_idempotent_response(
    prefix: str,
    user_id: str,
    request: Request,
    response_data: dict,
) -> None:
    key = get_idempotency_key(request)
    if key:
        redis_key = idempotency_key_for(prefix, user_id, key)
        await store_response(redis_key, response_data)