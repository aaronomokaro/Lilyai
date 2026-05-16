from fastapi import FastAPI
from app.core.database import engine
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="LilyAI",
    description="Enterprise grade document intelligence. Accessible to everyone.",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok", "env": settings.APP_ENV}