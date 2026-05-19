import datetime
from typing import Optional
from uuid import UUID

import httpx
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.integration import IntegrationToken

settings = get_settings()


def get_fernet() -> Fernet:
    return Fernet(settings.FERNET_KEY.encode())


def encrypt_token(token: str) -> str:
    f = get_fernet()
    return f.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    f = get_fernet()
    return f.decrypt(encrypted_token.encode()).decode()


def get_integration_token(
    user_id: str,
    provider: str,
    db: Session,
) -> Optional[IntegrationToken]:
    return (
        db.query(IntegrationToken)
        .filter(
            IntegrationToken.user_id == UUID(user_id),
            IntegrationToken.provider == provider,
            IntegrationToken.is_active == True,
        )
        .first()
    )


def store_integration_token(
    user_id: str,
    organisation_id: Optional[str],
    provider: str,
    access_token: str,
    refresh_token: Optional[str],
    scopes: Optional[str],
    expires_at: Optional[datetime.datetime],
    db: Session,
) -> IntegrationToken:
    # Check if token already exists - update rather than create duplicate
    existing = get_integration_token(user_id, provider, db)

    encrypted_access = encrypt_token(access_token)
    encrypted_refresh = encrypt_token(refresh_token) if refresh_token else None

    if existing:
        existing.encrypted_access_token = encrypted_access
        existing.encrypted_refresh_token = encrypted_refresh
        existing.scopes = scopes
        existing.token_expires_at = expires_at
        db.commit()
        return existing

    token_record = IntegrationToken(
        user_id=UUID(user_id),
        organisation_id=UUID(organisation_id) if organisation_id else None,
        provider=provider,
        encrypted_access_token=encrypted_access,
        encrypted_refresh_token=encrypted_refresh,
        scopes=scopes,
        token_expires_at=expires_at,
    )
    db.add(token_record)
    db.commit()
    return token_record


def disconnect_integration(
    user_id: str,
    provider: str,
    db: Session,
) -> None:
    token = get_integration_token(user_id, provider, db)
    if token:
        token.is_active = False
        db.commit()


async def send_gmail(
    user_id: str,
    provider: str,
    to_email: str,
    subject: str,
    body: str,
    attachment_s3_key: Optional[str],
    db: Session,
) -> dict:
    token_record = get_integration_token(user_id, "gmail", db)

    if not token_record:
        return {
            "success": False,
            "error": "Gmail not connected. Please connect Gmail in settings.",
        }

    access_token = decrypt_token(token_record.encrypted_access_token)

    # Build Gmail API request
    import base64
    from email.mime.text import MIMEText

    message = MIMEText(body)
    message["to"] = to_email
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"raw": raw},
        )

    if response.status_code == 200:
        return {"success": True, "message": f"Email sent to {to_email}"}
    else:
        return {"success": False, "error": f"Gmail API error: {response.status_code}"}


async def save_to_drive(
    user_id: str,
    filename: str,
    content: bytes,
    mime_type: str,
    db: Session,
) -> dict:
    token_record = get_integration_token(user_id, "drive", db)

    if not token_record:
        return {
            "success": False,
            "error": "Google Drive not connected. Please connect Drive in settings.",
        }

    access_token = decrypt_token(token_record.encrypted_access_token)

    metadata = {"name": filename}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
            headers={"Authorization": f"Bearer {access_token}"},
            files={
                "metadata": (None, str(metadata), "application/json"),
                "file": (filename, content, mime_type),
            },
        )

    if response.status_code in [200, 201]:
        file_id = response.json().get("id")
        return {"success": True, "file_id": file_id, "filename": filename}
    else:
        return {"success": False, "error": f"Drive API error: {response.status_code}"}
