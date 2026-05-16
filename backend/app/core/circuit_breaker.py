import time
from enum import Enum
from typing import Any, Callable

from fastapi import HTTPException, status


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int,
        timeout: int,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    def _should_attempt_reset(self) -> bool:
        return (
            self.last_failure_time is not None
            and time.time() - self.last_failure_time >= self.timeout
        )

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def can_attempt(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        if self.state == CircuitState.HALF_OPEN:
            return True
        return False

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        if not self.can_attempt():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{self.name} is currently unavailable. Please try again later.",
            )
        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise e


# One circuit breaker per external dependency
anthropic_breaker = CircuitBreaker(
    name="Anthropic API",
    failure_threshold=5,
    timeout=60,
)

voyage_breaker = CircuitBreaker(
    name="Voyage AI",
    failure_threshold=3,
    timeout=30,
)

qdrant_breaker = CircuitBreaker(
    name="Qdrant",
    failure_threshold=5,
    timeout=45,
)

gmail_breaker = CircuitBreaker(
    name="Gmail MCP",
    failure_threshold=3,
    timeout=120,
)

drive_breaker = CircuitBreaker(
    name="Google Drive MCP",
    failure_threshold=3,
    timeout=120,
)

auth0_breaker = CircuitBreaker(
    name="Auth0",
    failure_threshold=3,
    timeout=30,
)
