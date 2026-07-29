import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()

token_auth_scheme = HTTPBearer()


async def get_jwks() -> dict:
    url = f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()


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
