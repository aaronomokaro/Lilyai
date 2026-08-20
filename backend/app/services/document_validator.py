from pathlib import Path

import magic
from fastapi import HTTPException, status

# Allowed file types and their magic bytes signatures
ALLOWED_TYPES = {
    "application/pdf": [b"%PDF"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
        b"PK\x03\x04"
    ],
    "text/plain": [],
}

# Tokens per page estimate - conservative estimate for dense documents
TOKENS_PER_PAGE_ESTIMATE = 500

MAX_FILENAME_LENGTH = 255


def validate_file_type(file_content: bytes, filename: str) -> str:
    mime = magic.from_buffer(file_content[:2048], mime=True)

    if mime not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not supported. Allowed types: PDF, Word documents, plain text.",
        )

    extension = Path(filename).suffix.lower()
    expected_extensions = {
        "application/pdf": [".pdf"],
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
            ".docx"
        ],
        "text/plain": [".txt"],
    }

    if extension not in expected_extensions.get(mime, []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension does not match file content.",
        )

    return mime


def validate_file_size(file_content: bytes, max_size_mb: int) -> None:
    file_size_mb = len(file_content) / (1024 * 1024)
    if file_size_mb > max_size_mb:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size {file_size_mb:.1f}MB exceeds your plan limit of {max_size_mb}MB.",
        )


def estimate_token_count(page_count: int) -> int:
    return page_count * TOKENS_PER_PAGE_ESTIMATE


def validate_token_budget(page_count: int, max_pages: int) -> None:
    if page_count > max_pages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document has {page_count} pages which exceeds your plan limit of {max_pages} pages.",
        )

    estimated_tokens = estimate_token_count(page_count)
    # Flag if document would produce extremely large token count
    if estimated_tokens > 150000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document estimated token count ({estimated_tokens:,}) exceeds processing limit.",
        )


def validate_filename(filename: str) -> None:
    if len(filename) > MAX_FILENAME_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Filename too long. Maximum {MAX_FILENAME_LENGTH} characters.",
        )

    dangerous_chars = ["../", "..\\", "/", "\\", "\x00"]
    for char in dangerous_chars:
        if char in filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename.",
            )


def basic_malware_check(file_content: bytes) -> None:
    # NOTE: This is a basic check only.
    # Before enterprise clients: replace with ClamAV or AWS GuardDuty integration.

    # Text-based injection patterns - check the start of the file only.
    text_patterns = [
        b"<script",
        b"javascript:",
        b"vbscript:",
    ]
    file_start = file_content[:1024].lower()
    for pattern in text_patterns:
        if pattern in file_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File failed security check.",
            )

    # Windows PE executables begin with the exact bytes "MZ".
    # Only reject if the file actually STARTS with this header,
    # not if the bytes appear anywhere inside a legitimate document.
    if file_content[:2] == b"\x4d\x5a":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File failed security check.",
        )


def validate_document(
    file_content: bytes,
    filename: str,
    max_size_mb: int,
    max_pages: int,
    page_count: int,
) -> str:
    validate_filename(filename)
    mime_type = validate_file_type(file_content, filename)
    validate_file_size(file_content, max_size_mb)
    validate_token_budget(page_count, max_pages)
    basic_malware_check(file_content)
    return mime_type
