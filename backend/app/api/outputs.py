import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.organisation import User
from app.models.output import Output
from app.services.s3_service import generate_presigned_url

router = APIRouter(prefix="/outputs", tags=["outputs"])


@router.get("/")
async def list_outputs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    outputs = (
        db.query(Output)
        .filter(Output.user_id == current_user.id)
        .order_by(Output.created_at.desc())
        .all()
    )

    return [
        {
            "id": str(output.id),
            "output_type": output.output_type,
            "format": output.format,
            "status": output.status,
            "is_permanent": output.is_permanent,
            "expires_at": output.expires_at.isoformat() if output.expires_at else None,
            "created_at": output.created_at.isoformat(),
        }
        for output in outputs
    ]


@router.get("/{output_id}/download")
async def get_download_url(
    output_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    output = (
        db.query(Output)
        .filter(
            Output.id == output_id,
            Output.user_id == current_user.id,
            Output.status == "ready",
        )
        .first()
    )

    if not output:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Output not found.",
        )

    import datetime

    if output.expires_at and output.expires_at < datetime.datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This output has expired. Free and Starter plan outputs are available for 24 hours.",
        )

    download_url = await generate_presigned_url(
        s3_key=output.s3_key,
        expiry_seconds=900,
    )

    return {
        "output_id": str(output_id),
        "download_url": download_url,
        "expires_in_seconds": 900,
    }
