from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from slowapi.errors import RateLimitExceeded

from app.api.collections import router as collections_router
from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.evaluation import router as evaluation_router
from app.api.integrations import router as integrations_router
from app.api.outputs import router as outputs_router
from app.api.queries import router as queries_router
from app.api.tags import router as tags_router
from app.api.usage import router as usage_router
from app.core.config import get_settings
from app.core.dependencies import get_current_user
from app.core.middleware import SecurityMiddleware
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.core.scheduler import setup_scheduler
from app.models.organisation import User
from app.services.websocket_service import manager

settings = get_settings()

app = FastAPI(
    title="LilyAI",
    description="Enterprise grade document intelligence. Accessible to everyone.",
    version="0.1.0",
)

from app.core.middleware import SecurityMiddleware

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


@app.on_event("startup")
async def startup_event():
    from app.services.qdrant_service import ensure_collection_exists
    ensure_collection_exists()
    scheduler = setup_scheduler()
    scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    from app.core.scheduler import scheduler

    scheduler.shutdown()


app.include_router(documents_router)
app.include_router(queries_router)

app.include_router(collections_router)
app.include_router(tags_router)
app.include_router(integrations_router)

app.include_router(conversations_router)
app.include_router(outputs_router)
app.include_router(usage_router)

app.include_router(evaluation_router)


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
