from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

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
from app.core.database import SessionLocal
from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.core.scheduler import setup_scheduler
from app.core.security import verify_token_string
from app.models.organisation import User
from app.services.websocket_service import manager

settings = get_settings()

app = FastAPI(
    title="LilyAI",
    description="Enterprise grade document intelligence. Accessible to everyone.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    # Authenticate at handshake. Browsers can't set headers on WS connections,
    # so the token is passed as a query param: /ws/{user_id}?token=xxx
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)  # 4401 = unauthenticated
        return

    try:
        payload = await verify_token_string(token)
    except Exception:
        await websocket.close(code=4401)
        return

    # The token must belong to the user whose stream is being connected to.
    # This blocks connecting to /ws/{someone_elses_id}.
    token_user = payload.get("sub")
    if not token_user:
        await websocket.close(code=4401)
        return

    # Resolve the token's auth0 id to the internal user id and confirm match.
    db = SessionLocal()
    try:
        db_user = (
            db.query(User)
            .from_statement(text("SELECT * FROM get_user_by_auth0_id(:auth0_id)"))
            .params(auth0_id=token_user)
            .first()
        )
    finally:
        db.close()

    if not db_user or str(db_user.id) != str(user_id):
        await websocket.close(code=4403)  # 4403 = forbidden (wrong user)
        return

    await manager.connect(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id)
