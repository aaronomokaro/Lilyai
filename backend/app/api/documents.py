import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.cache import cache_get, key_subscription
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_test_user
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
    current_user: User = Depends(get_test_user),
):
    cached = await check_idempotency(
        prefix="document_upload",
        user_id=str(current_user.id),
        request=request,
    )
    if cached:
        return cached

    file_content = await file.read()
    subscription = await get_user_subscription(current_user, db)

    from app.services.document_validator import validate_file_type

    mime_type = validate_file_type(file_content, file.filename)
    page_count = get_page_count(file_content, mime_type)

    mime_type = validate_document(
        file_content=file_content,
        filename=file.filename,
        max_size_mb=subscription.max_file_size_mb,
        max_pages=subscription.max_pages_per_doc,
        page_count=page_count,
    )

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

    await upload_document(
        file_content=file_content,
        s3_key=s3_key,
        content_type=mime_type,
    )

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

    processing_job = ProcessingJob(
        document_id=doc_id,
        user_id=current_user.id,
        status="pending",
    )
    db.add(processing_job)
    db.commit()

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

    await save_idempotent_response(
        prefix="document_upload",
        user_id=str(current_user.id),
        request=request,
        response_data=response_data,
    )

    return response_data


@router.get("/search/")
async def search_documents(
    q: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not q or len(q.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query must be at least 2 characters.",
        )

    documents = (
        db.query(Document)
        .filter(
            Document.user_id == current_user.id,
            Document.is_active == True,
            Document.filename.ilike(f"%{q}%"),
        )
        .order_by(Document.created_at.desc())
        .limit(20)
        .all()
    )

    return [
        {
            "id": str(doc.id),
            "filename": doc.filename,
            "file_type": doc.file_type,
            "status": doc.status,
            "created_at": doc.created_at.isoformat(),
        }
        for doc in documents
    ]


@router.get("/")
async def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    documents = (
        db.query(Document)
        .filter(
            Document.user_id == current_user.id,
            Document.is_active == True,
        )
        .order_by(Document.created_at.desc())
        .all()
    )

    return [
        {
            "id": str(doc.id),
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size_bytes": doc.file_size_bytes,
            "page_count": doc.page_count,
            "status": doc.status,
            "created_at": doc.created_at.isoformat(),
        }
        for doc in documents
    ]


@router.get("/{document_id}")
async def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id,
            Document.is_active == True,
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    return {
        "id": str(document.id),
        "filename": document.filename,
        "file_type": document.file_type,
        "file_size_bytes": document.file_size_bytes,
        "page_count": document.page_count,
        "status": document.status,
        "doc_type": document.doc_type,
        "created_at": document.created_at.isoformat(),
    }


@router.delete("/{document_id}", status_code=204)
async def archive_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == current_user.id,
            Document.is_active == True,
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    document.is_active = False
    db.commit()
