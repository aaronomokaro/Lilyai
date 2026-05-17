import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, status

from app.core.config import get_settings

settings = get_settings()


def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )


def build_s3_key(org_id: str, user_id: str, doc_id: str, filename: str) -> str:
    return f"{org_id}/{user_id}/{doc_id}/{filename}"


async def upload_document(
    file_content: bytes,
    s3_key: str,
    content_type: str,
) -> str:
    client = get_s3_client()
    try:
        client.put_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType=content_type,
        )
        return s3_key
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document to storage: {str(e)}",
        )


async def download_document(s3_key: str) -> bytes:
    client = get_s3_client()
    try:
        response = client.get_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=s3_key,
        )
        return response["Body"].read()
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found in storage: {str(e)}",
        )


async def generate_presigned_url(s3_key: str, expiry_seconds: int = 900) -> str:
    client = get_s3_client()
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.AWS_S3_BUCKET,
                "Key": s3_key,
            },
            ExpiresIn=expiry_seconds,
        )
        return url
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate download URL: {str(e)}",
        )


async def delete_document(s3_key: str) -> None:
    client = get_s3_client()
    try:
        client.delete_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=s3_key,
        )
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document from storage: {str(e)}",
        )
