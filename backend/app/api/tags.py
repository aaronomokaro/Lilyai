import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_rls_db
from app.models.document import Document, DocumentTag, Tag
from app.models.organisation import User

router = APIRouter(prefix="/tags", tags=["tags"])


class TagCreate(BaseModel):
    name: str
    color: Optional[str] = None


class TagUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


class AssignTagRequest(BaseModel):
    document_id: uuid.UUID


@router.post("/", status_code=201)
async def create_tag(
    request: TagCreate,
    db: Session = Depends(get_rls_db),
    current_user: User = Depends(get_current_user),
):
    if request.color and not request.color.startswith("#"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Color must be a hex code starting with #",
        )

    tag = Tag(
        user_id=current_user.id,
        organisation_id=current_user.organisation_id,
        name=request.name,
        color=request.color,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)

    return {
        "id": str(tag.id),
        "name": tag.name,
        "color": tag.color,
        "created_at": tag.created_at.isoformat(),
    }


@router.get("/")
async def list_tags(
    db: Session = Depends(get_rls_db),
    current_user: User = Depends(get_current_user),
):
    tags = (
        db.query(Tag)
        .filter(
            Tag.user_id == current_user.id,
        )
        .all()
    )

    return [
        {
            "id": str(tag.id),
            "name": tag.name,
            "color": tag.color,
            "created_at": tag.created_at.isoformat(),
        }
        for tag in tags
    ]


@router.patch("/{tag_id}")
async def update_tag(
    tag_id: uuid.UUID,
    request: TagUpdate,
    db: Session = Depends(get_rls_db),
    current_user: User = Depends(get_current_user),
):
    tag = (
        db.query(Tag)
        .filter(
            Tag.id == tag_id,
            Tag.user_id == current_user.id,
        )
        .first()
    )

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found.",
        )

    if request.name is not None:
        tag.name = request.name
    if request.color is not None:
        if not request.color.startswith("#"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Color must be a hex code starting with #",
            )
        tag.color = request.color

    db.commit()

    return {"id": str(tag.id), "name": tag.name, "color": tag.color}


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: uuid.UUID,
    db: Session = Depends(get_rls_db),
    current_user: User = Depends(get_current_user),
):
    tag = (
        db.query(Tag)
        .filter(
            Tag.id == tag_id,
            Tag.user_id == current_user.id,
        )
        .first()
    )

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found.",
        )

    db.query(DocumentTag).filter(DocumentTag.tag_id == tag_id).delete()
    db.delete(tag)
    db.commit()


@router.post("/{tag_id}/assign")
async def assign_tag_to_document(
    tag_id: uuid.UUID,
    request: AssignTagRequest,
    db: Session = Depends(get_rls_db),
    current_user: User = Depends(get_current_user),
):
    tag = (
        db.query(Tag)
        .filter(
            Tag.id == tag_id,
            Tag.user_id == current_user.id,
        )
        .first()
    )

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found.",
        )

    document = (
        db.query(Document)
        .filter(
            Document.id == request.document_id,
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

    existing = (
        db.query(DocumentTag)
        .filter(
            DocumentTag.tag_id == tag_id,
            DocumentTag.document_id == request.document_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tag already assigned to this document.",
        )

    document_tag = DocumentTag(
        document_id=request.document_id,
        tag_id=tag_id,
    )
    db.add(document_tag)
    db.commit()

    return {"message": "Tag assigned to document."}


@router.delete("/{tag_id}/assign/{document_id}", status_code=204)
async def remove_tag_from_document(
    tag_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_rls_db),
    current_user: User = Depends(get_current_user),
):
    tag = (
        db.query(Tag)
        .filter(
            Tag.id == tag_id,
            Tag.user_id == current_user.id,
        )
        .first()
    )

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found.",
        )

    document_tag = (
        db.query(DocumentTag)
        .filter(
            DocumentTag.tag_id == tag_id,
            DocumentTag.document_id == document_id,
        )
        .first()
    )

    if not document_tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not assigned to this document.",
        )

    db.delete(document_tag)
    db.commit()
