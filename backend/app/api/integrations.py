import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.organisation import User
from app.models.subscription import Subscription
from app.services.integration_service import (
    disconnect_integration,
    get_integration_token,
    save_to_drive,
    send_gmail,
    store_integration_token,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])

DRIVE_MINIMUM_PLAN = "starter"
PLAN_ORDER = ["free", "starter", "professional", "enterprise"]


def get_user_plan(user: User, db: Session) -> str:
    subscription = (
        db.query(Subscription).filter(Subscription.user_id == user.id).first()
    )
    return subscription.plan if subscription else "free"


def plan_meets_minimum(user_plan: str, minimum_plan: str) -> bool:
    user_level = PLAN_ORDER.index(user_plan) if user_plan in PLAN_ORDER else 0
    min_level = PLAN_ORDER.index(minimum_plan) if minimum_plan in PLAN_ORDER else 0
    return user_level >= min_level


class OAuthCallbackRequest(BaseModel):
    provider: str
    access_token: str
    refresh_token: Optional[str] = None
    scopes: Optional[str] = None


class SendEmailRequest(BaseModel):
    to_email: str
    subject: str
    body: str
    output_id: Optional[str] = None


class SaveToDriveRequest(BaseModel):
    output_id: str
    filename: str


@router.get("/status")
async def get_integration_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    gmail_token = get_integration_token(str(current_user.id), "gmail", db)
    drive_token = get_integration_token(str(current_user.id), "drive", db)
    user_plan = get_user_plan(current_user, db)

    return {
        "gmail": {
            "connected": gmail_token is not None,
            "available": True,
        },
        "drive": {
            "connected": drive_token is not None,
            "available": plan_meets_minimum(user_plan, DRIVE_MINIMUM_PLAN),
        },
    }


@router.post("/callback")
async def oauth_callback(
    request: OAuthCallbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if request.provider == "drive":
        user_plan = get_user_plan(current_user, db)
        if not plan_meets_minimum(user_plan, DRIVE_MINIMUM_PLAN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Google Drive integration requires Starter plan or above.",
            )

    store_integration_token(
        user_id=str(current_user.id),
        organisation_id=(
            str(current_user.organisation_id) if current_user.organisation_id else None
        ),
        provider=request.provider,
        access_token=request.access_token,
        refresh_token=request.refresh_token,
        scopes=request.scopes,
        expires_at=None,
        db=db,
    )

    return {"message": f"{request.provider.title()} connected successfully."}


@router.delete("/{provider}/disconnect", status_code=204)
async def disconnect(
    provider: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if provider not in ["gmail", "drive"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid provider. Must be gmail or drive.",
        )

    disconnect_integration(str(current_user.id), provider, db)


@router.post("/gmail/send")
async def send_via_gmail(
    request: SendEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await send_gmail(
        user_id=str(current_user.id),
        provider="gmail",
        to_email=request.to_email,
        subject=request.subject,
        body=request.body,
        attachment_s3_key=None,
        db=db,
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result["error"],
        )

    return result


@router.post("/drive/save")
async def save_output_to_drive(
    request: SaveToDriveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_plan = get_user_plan(current_user, db)
    if not plan_meets_minimum(user_plan, DRIVE_MINIMUM_PLAN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google Drive integration requires Starter plan or above.",
        )

    from uuid import UUID

    from app.models.output import Output
    from app.services.s3_service import download_document

    output = (
        db.query(Output)
        .filter(
            Output.id == UUID(request.output_id),
            Output.user_id == current_user.id,
        )
        .first()
    )

    if not output:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Output not found.",
        )

    file_content = await download_document(output.s3_key)

    result = await save_to_drive(
        user_id=str(current_user.id),
        filename=request.filename,
        content=file_content,
        mime_type="text/plain",
        db=db,
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result["error"],
        )

    return result
