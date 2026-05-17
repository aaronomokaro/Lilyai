import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.cache import cache_get, key_subscription
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.idempotency import check_idempotency, save_idempotent_response
from app.models.document import Document
from app.models.organisation import User
from app.models.processing import ProcessingJob
from app.models.subscription import Subscription
from app.services.document_extractor import get_page_count
from app.services.document_validator import validate_document
from app.services.s3_service import build_s3_key, upload_document
from app.workers.document_processor import process_document

router = APIRouter(prefix="/documents", tags=["documents"])


async def get_user_subscription(user: User, db: Session) -> Subscription:
    subscription = (
        db.query(Subscription).filter(Subscription.user_id == user.id).first()
    )

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active subscription found.",
        )

    return subscription


@router.post("/upload", status_code=202)
async def upload_document_endpoint(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check idempotency - prevent duplicate uploads on retry
    cached = await check_idempotency(
        prefix="document_upload",
        user_id=str(current_user.id),
        request=request,
    )
    if cached:
        return cached

    # Read file content into memory
    file_content = await file.read()

    # Get user subscription for plan limits
    subscription = await get_user_subscription(current_user, db)

    # Get page count before full validation
    from app.services.document_validator import validate_file_type

    mime_type = validate_file_type(file_content, file.filename)
    page_count = get_page_count(file_content, mime_type)

    # Validate document against plan limits
    mime_type = validate_document(
        file_content=file_content,
        filename=file.filename,
        max_size_mb=subscription.max_file_size_mb,
        max_pages=subscription.max_pages_per_doc,
        page_count=page_count,
    )

    # Generate document ID and build S3 key
    doc_id = uuid.uuid4()
    org_id = (
        str(current_user.organisation_id)
        if current_user.organisation_id
        else str(current_user.id)
    )
    s3_key = build_s3_key(
        org_id=org_id,
        user_id=str(current_user.id),
        doc_id=str(doc_id),
        filename=file.filename,
    )

    # Upload to S3
    await upload_document(
        file_content=file_content,
        s3_key=s3_key,
        content_type=mime_type,
    )

    # Create document record in PostgreSQL
    document = Document(
        id=doc_id,
        user_id=current_user.id,
        organisation_id=current_user.organisation_id,
        filename=file.filename,
        original_filename=file.filename,
        file_type=mime_type,
        file_size_bytes=len(file_content),
        page_count=page_count,
        s3_key=s3_key,
        status="pending",
    )
    db.add(document)

    # Create processing job record
    processing_job = ProcessingJob(
        document_id=doc_id,
        user_id=current_user.id,
        status="pending",
    )
    db.add(processing_job)
    db.commit()

    # Queue Celery background task
    process_document.delay(
        document_id=str(doc_id),
        user_id=str(current_user.id),
        organisation_id=(
            str(current_user.organisation_id) if current_user.organisation_id else None
        ),
    )

    response_data = {
        "document_id": str(doc_id),
        "filename": file.filename,
        "status": "pending",
        "message": "Document uploaded successfully. Processing will begin shortly.",
    }

    # Store idempotent response
    await save_idempotent_response(
        prefix="document_upload",
        user_id=str(current_user.id),
        request=request,
        response_data=response_data,
    )

    return response_data
