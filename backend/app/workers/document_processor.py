import uuid

from celery import Celery

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.processing import Chunk, ProcessingJob
from app.services.chunking_service import chunk_document
from app.services.document_extractor import extract_text
from app.services.embedding_service import embed_chunks
from app.services.qdrant_service import ensure_collection_exists, store_chunks
from app.services.s3_service import download_document

settings = get_settings()

celery_app = Celery(
    "lilyai",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="process_document",
)
def process_document(self, document_id: str, user_id: str, organisation_id: str = None):
    # Import here to avoid circular imports - websocket manager lives in the
    # FastAPI app but the worker runs in a separate process
    from app.services.websocket_service import manager

    db = SessionLocal()
    document = None
    job = None

    try:
        # Step 1 - mark job as started
        job = (
            db.query(ProcessingJob)
            .filter(ProcessingJob.document_id == uuid.UUID(document_id))
            .first()
        )

        if job:
            job.status = "processing"
            job.celery_task_id = self.request.id
            db.commit()

        # Step 2 - fetch document record
        document = (
            db.query(Document).filter(Document.id == uuid.UUID(document_id)).first()
        )

        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Step 3 - download from S3
        file_content = await_sync(download_document(document.s3_key))

        # Step 4 - extract text
        text = extract_text(file_content, document.file_type)

        if not text.strip():
            raise ValueError("Document contains no extractable text")

        # Step 5 - chunk the text
        chunks = chunk_document(
            text=text,
            document_id=uuid.UUID(document_id),
            user_id=uuid.UUID(user_id),
            organisation_id=uuid.UUID(organisation_id) if organisation_id else None,
        )

        if job:
            job.chunks_total = len(chunks)
            db.commit()

        # Step 6 - embed chunks
        embedded_chunks = await_sync(embed_chunks(chunks))

        # Step 7 - ensure Qdrant collection exists and store vectors
        ensure_collection_exists()
        store_chunks(embedded_chunks)

        # Step 8 - store chunks in PostgreSQL
        chunk_records = []
        for chunk in embedded_chunks:
            chunk_records.append(
                Chunk(
                    id=chunk["id"],
                    document_id=uuid.UUID(document_id),
                    user_id=uuid.UUID(user_id),
                    organisation_id=(
                        uuid.UUID(organisation_id) if organisation_id else None
                    ),
                    content=chunk["content"],
                    chunk_index=chunk["chunk_index"],
                    token_count=chunk.get("token_count"),
                    qdrant_id=str(chunk["id"]),
                )
            )

        db.bulk_save_objects(chunk_records)

        # Step 9 - update document and job status
        document.status = "ready"
        if job:
            job.status = "completed"
            job.chunks_processed = len(chunks)
        db.commit()

        # Step 10 - notify frontend via WebSocket
        await_sync(
            manager.send_document_ready(
                user_id=user_id,
                document_id=document_id,
                filename=document.filename,
            )
        )

    except Exception as exc:
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            db.commit()

        if document:
            document.status = "failed"
            db.commit()

        # Notify frontend of failure
        await_sync(
            manager.send_document_failed(
                user_id=user_id,
                document_id=document_id,
                filename=document.filename if document else "Unknown",
            )
        )

        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))

    finally:
        db.close()


def await_sync(coroutine):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()
