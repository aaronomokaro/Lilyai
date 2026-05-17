from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from slowapi.errors import RateLimitExceeded

from app.api.documents import router as documents_router
from app.core.config import get_settings
from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.models.organisation import User
from app.services.websocket_service import manager

settings = get_settings()

app = FastAPI(
    title="LilyAI",
    description="Enterprise grade document intelligence. Accessible to everyone.",
    version="0.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.include_router(documents_router)


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


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    try:
        while True:
            # Keep connection alive - wait for any message from client
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id)
