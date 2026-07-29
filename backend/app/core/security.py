import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()

token_auth_scheme = HTTPBearer()


JWKS_CACHE_KEY = "auth0:jwks"
JWKS_CACHE_TTL = 3600  # 1 hour - Auth0 signing keys rotate rarely


async def get_jwks() -> dict:
    import json

    import redis.asyncio as aioredis

    url = f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json"

    # Try the Redis cache first - avoids a network round-trip to Auth0
    # on every single token verification.
    try:
        redis = await aioredis.from_url(settings.REDIS_URL)
        cached = await redis.get(JWKS_CACHE_KEY)
        if cached:
            await redis.close()
            return json.loads(cached)
    except Exception:
        # If Redis is unavailable, fall through to fetching directly -
        # caching is an optimisation, not a hard dependency.
        redis = None

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        jwks = response.json()

    # Store in cache for next time (best-effort).
    try:
        if redis is not None:
            await redis.set(JWKS_CACHE_KEY, json.dumps(jwks), ex=JWKS_CACHE_TTL)
            await redis.close()
    except Exception:
        pass

    return jwks


async def verify_token_string(token: str) -> dict:
    """
    Verify a raw JWT string and return its payload. Shared verification used by
    both the HTTP dependency (verify_token) and the WebSocket handshake, so the
    JWKS/decode logic lives in one place.
    """
    try:
        jwks = await get_jwks()
        unverified_header = jwt.get_unverified_header(token)

        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break

        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find appropriate key",
            )

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=[settings.AUTH0_ALGORITHMS],
            audience=settings.AUTH0_API_AUDIENCE,
            issuer=f"https://{settings.AUTH0_DOMAIN}/",
        )

        return payload

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(token_auth_scheme),
) -> dict:
    return await verify_token_string(credentials.credentials)
