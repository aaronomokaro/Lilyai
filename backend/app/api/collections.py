import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.document import Collection, CollectionDocument, Document
from app.models.organisation import User

router = APIRouter(prefix="/collections", tags=["collections"])


class CollectionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None


class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class AddDocumentRequest(BaseModel):
    document_id: uuid.UUID


@router.post("/", status_code=201)
async def create_collection(
    request: CollectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if request.parent_id:
        parent = (
            db.query(Collection)
            .filter(
                Collection.id == request.parent_id,
                Collection.user_id == current_user.id,
                Collection.is_active == True,
            )
            .first()
        )

        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent collection not found.",
            )

        if parent.parent_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Collections only support one level of nesting.",
            )

    collection = Collection(
        user_id=current_user.id,
        organisation_id=current_user.organisation_id,
        name=request.name,
        description=request.description,
        parent_id=request.parent_id,
    )
    db.add(collection)
    db.commit()
    db.refresh(collection)

    return {
        "id": str(collection.id),
        "name": collection.name,
        "description": collection.description,
        "parent_id": str(collection.parent_id) if collection.parent_id else None,
        "created_at": collection.created_at.isoformat(),
    }


@router.get("/")
async def list_collections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    collections = (
        db.query(Collection)
        .filter(
            Collection.user_id == current_user.id,
            Collection.is_active == True,
            Collection.parent_id == None,
        )
        .all()
    )

    result = []
    for col in collections:
        children = (
            db.query(Collection)
            .filter(
                Collection.parent_id == col.id,
                Collection.is_active == True,
            )
            .all()
        )

        result.append(
            {
                "id": str(col.id),
                "name": col.name,
                "description": col.description,
                "children": [
                    {"id": str(c.id), "name": c.name, "description": c.description}
                    for c in children
                ],
                "created_at": col.created_at.isoformat(),
            }
        )

    return result


@router.patch("/{collection_id}")
async def update_collection(
    collection_id: uuid.UUID,
    request: CollectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    collection = (
        db.query(Collection)
        .filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.id,
            Collection.is_active == True,
        )
        .first()
    )

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found.",
        )

    if request.name is not None:
        collection.name = request.name
    if request.description is not None:
        collection.description = request.description

    db.commit()

    return {
        "id": str(collection.id),
        "name": collection.name,
        "description": collection.description,
    }


@router.delete("/{collection_id}", status_code=204)
async def archive_collection(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    collection = (
        db.query(Collection)
        .filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.id,
            Collection.is_active == True,
        )
        .first()
    )

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found.",
        )

    # Archive not delete - architecture requirement
    collection.is_active = False

    # Archive children too
    db.query(Collection).filter(
        Collection.parent_id == collection_id,
    ).update({"is_active": False})

    db.commit()


@router.post("/{collection_id}/documents")
async def add_document_to_collection(
    collection_id: uuid.UUID,
    request: AddDocumentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    collection = (
        db.query(Collection)
        .filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.id,
            Collection.is_active == True,
        )
        .first()
    )

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found.",
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
        db.query(CollectionDocument)
        .filter(
            CollectionDocument.collection_id == collection_id,
            CollectionDocument.document_id == request.document_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document already in this collection.",
        )

    collection_document = CollectionDocument(
        collection_id=collection_id,
        document_id=request.document_id,
    )
    db.add(collection_document)
    db.commit()

    return {"message": "Document added to collection."}


@router.delete("/{collection_id}/documents/{document_id}", status_code=204)
async def remove_document_from_collection(
    collection_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    collection = (
        db.query(Collection)
        .filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.id,
        )
        .first()
    )

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found.",
        )

    collection_document = (
        db.query(CollectionDocument)
        .filter(
            CollectionDocument.collection_id == collection_id,
            CollectionDocument.document_id == document_id,
        )
        .first()
    )

    if not collection_document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not in this collection.",
        )

    db.delete(collection_document)
    db.commit()


@router.get("/{collection_id}/document-ids")
async def get_collection_document_ids(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    collection = (
        db.query(Collection)
        .filter(
            Collection.id == collection_id,
            Collection.user_id == current_user.id,
            Collection.is_active == True,
        )
        .first()
    )

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found.",
        )

    collection_documents = (
        db.query(CollectionDocument)
        .filter(
            CollectionDocument.collection_id == collection_id,
        )
        .all()
    )

    return {
        "collection_id": str(collection_id),
        "document_ids": [str(cd.document_id) for cd in collection_documents],
    }
