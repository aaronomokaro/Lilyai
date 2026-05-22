import re
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Maximum request body size - 50MB covers largest Enterprise file uploads
MAX_REQUEST_SIZE_BYTES = 50 * 1024 * 1024

# SQL injection patterns to detect in query parameters
SQL_INJECTION_PATTERNS = [
    r"(\bUNION\b.*\bSELECT\b)",
    r"(\bDROP\b.*\bTABLE\b)",
    r"(\bINSERT\b.*\bINTO\b)",
    r"(\bDELETE\b.*\bFROM\b)",
    r"(--|#|/\*|\*/)",
    r"(\bOR\b.*=.*\bOR\b)",
    r"(\bAND\b.*=.*\bAND\b)",
    r"(;.*\bDROP\b)",
    r"(\bEXEC\b.*\()",
    r"(\bxp_\w+)",
]

# Compile patterns once at startup for performance
COMPILED_SQL_PATTERNS = [
    re.compile(pattern, re.IGNORECASE) for pattern in SQL_INJECTION_PATTERNS
]

# Dangerous characters in path parameters
DANGEROUS_PATH_CHARS = ["../", "..\\", "\x00", "%00", "%2e%2e"]


def contains_sql_injection(value: str) -> bool:
    for pattern in COMPILED_SQL_PATTERNS:
        if pattern.search(value):
            return True
    return False


def contains_path_traversal(value: str) -> bool:
    value_lower = value.lower()
    for char in DANGEROUS_PATH_CHARS:
        if char in value_lower:
            return True
    return False


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Check request size before reading body
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_SIZE_BYTES:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large."},
            )

        # Check query parameters for SQL injection and path traversal
        for key, value in request.query_params.items():
            if contains_sql_injection(value):
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid request parameters."},
                )
            if contains_path_traversal(value):
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid request parameters."},
                )

        # Check path for path traversal
        if contains_path_traversal(request.url.path):
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid request path."},
            )

        # Add security headers to every response
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

        return response
