import json
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()


async def get_redis() -> aioredis.Redis:
    return await aioredis.from_url(settings.REDIS_URL)


async def cache_get(key: str) -> Optional[Any]:
    redis = await get_redis()
    data = await redis.get(key)
    await redis.aclose()
    if data:
        return json.loads(data)
    return None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    redis = await get_redis()
    await redis.set(key, json.dumps(value), ex=ttl)
    await redis.aclose()


async def cache_delete(key: str) -> None:
    redis = await get_redis()
    await redis.delete(key)
    await redis.aclose()


async def cache_delete_pattern(pattern: str) -> None:
    redis = await get_redis()
    keys = await redis.keys(pattern)
    if keys:
        await redis.delete(*keys)
    await redis.aclose()


# TTL constants from the architecture
TTL_SUBSCRIPTION = 900  # 15 minutes
TTL_FEATURE_FLAGS = 60  # 60 seconds
TTL_USER_PROFILE = 900  # 15 minutes
TTL_DOCUMENT_LIST = 300  # 5 minutes
TTL_CONVERSATION_LIST = 300  # 5 minutes
TTL_TOKEN_VERSION = 3600  # 1 hour


# Cache key helpers
def key_subscription(user_id: str) -> str:
    return f"subscription:{user_id}"


def key_feature_flag(flag_name: str) -> str:
    return f"feature_flag:{flag_name}"


def key_user_profile(user_id: str) -> str:
    return f"user_profile:{user_id}"


def key_document_list(user_id: str) -> str:
    return f"document_list:{user_id}"


def key_token_version(user_id: str) -> str:
    return f"token_version:{user_id}"
