import asyncio
from typing import List

import httpx
from fastapi import HTTPException, status

from app.core.circuit_breaker import voyage_breaker
from app.core.config import get_settings

settings = get_settings()

VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_MODEL = "voyage-3"
MAX_REQUESTS_PER_SECOND = 10
EMBEDDING_DIMENSION = 1024


async def embed_single(text: str) -> List[float]:
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                VOYAGE_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.VOYAGE_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": [text],
                    "model": VOYAGE_MODEL,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Embedding service error: {response.text}",
                )

            data = response.json()
            return data["data"][0]["embedding"]

    return await voyage_breaker.call(_call)


async def embed_chunks(chunks: List[dict]) -> List[dict]:
    semaphore = asyncio.Semaphore(MAX_REQUESTS_PER_SECOND)

    async def embed_with_throttle(chunk: dict) -> dict:
        async with semaphore:
            embedding = await embed_single(chunk["content"])
            chunk["embedding"] = embedding
            await asyncio.sleep(1 / MAX_REQUESTS_PER_SECOND)
            return chunk

    tasks = [embed_with_throttle(chunk) for chunk in chunks]
    return await asyncio.gather(*tasks)
