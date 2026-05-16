from fastapi import Depends, FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.models.organisation import User

settings = get_settings()

app = FastAPI(
    title="LilyAI",
    description="Enterprise grade document intelligence. Accessible to everyone.",
    version="0.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


@app.get("/health")
def health_check():
    return {"status": "ok", "env": settings.APP_ENV}


@app.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "role": current_user.role,
    }
