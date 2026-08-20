from typing import List

from fastapi import HTTPException, status
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from app.core.config import get_settings

settings = get_settings()

COLLECTION_NAME = "document_chunks"
VECTOR_SIZE = 1024


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )


def get_async_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )


def ensure_collection_exists() -> None:
    client = get_qdrant_client()
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    if COLLECTION_NAME not in collection_names:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )

    # Create payload indexes for filtering
    # Required for user_id, document_id, and organisation_id filters to work
    # try/except on each because the index may already exist on subsequent startups
    try:
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="user_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
    except Exception:
        pass

    try:
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="document_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
    except Exception:
        pass

    try:
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="organisation_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
    except Exception:
        pass


def store_chunks(chunks: List[dict]) -> None:
    client = get_qdrant_client()

    points = []
    for chunk in chunks:
        points.append(
            PointStruct(
                id=str(chunk["id"]),
                vector=chunk["embedding"],
                payload={
                    "document_id": str(chunk["document_id"]),
                    "user_id": str(chunk["user_id"]),
                    "organisation_id": (
                        str(chunk["organisation_id"])
                        if chunk.get("organisation_id")
                        else None
                    ),
                    "chunk_index": chunk["chunk_index"],
                    "page_number": chunk.get("page_number"),
                    "content": chunk["content"],
                },
            )
        )

    try:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store vectors: {str(e)}",
        )


async def search_chunks(
    query_vector: List[float],
    user_id: str,
    organisation_id: str = None,
    top_k: int = 5,
    document_ids: List[str] = None,
) -> List[dict]:
    client = get_async_qdrant_client()

    must_conditions = [
        FieldCondition(
            key="user_id",
            match=MatchValue(value=user_id),
        )
    ]

    if organisation_id:
        must_conditions.append(
            FieldCondition(
                key="organisation_id",
                match=MatchValue(value=organisation_id),
            )
        )

    if document_ids:
        must_conditions.append(
            FieldCondition(
                key="document_id",
                match=MatchAny(any=document_ids),
            )
        )

    results = await client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        query_filter=Filter(must=must_conditions),
        limit=top_k,
        with_payload=True,
    )
    await client.close()
    return [
        {
            "chunk_id": result.id,
            "document_id": result.payload["document_id"],
            "content": result.payload["content"],
            "chunk_index": result.payload["chunk_index"],
            "page_number": result.payload.get("page_number"),
            "score": result.score,
        }
        for result in results
    ]


def delete_document_chunks(document_id: str) -> None:
    client = get_qdrant_client()
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=document_id),
                )
            ]
        ),
    )
