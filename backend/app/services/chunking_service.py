import uuid
from typing import List

from app.models.processing import Chunk

# Chunking configuration
MIN_CHUNK_CHARS = 100  # Merge chunks shorter than this with neighbours
MAX_CHUNK_CHARS = 2000  # Split chunks longer than this
OVERLAP_CHARS = 100  # Overlap between chunks to preserve context across boundaries


def clean_text(text: str) -> str:
    # Remove excessive whitespace and normalize line endings
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        line = line.strip()
        if line:
            cleaned.append(line)
    return "\n".join(cleaned)


def split_into_paragraphs(text: str) -> List[str]:
    # Split on double newlines - standard paragraph separator
    paragraphs = text.split("\n\n")
    # Filter empty paragraphs and strip whitespace
    return [p.strip() for p in paragraphs if p.strip()]


def merge_short_paragraphs(paragraphs: List[str]) -> List[str]:
    merged = []
    buffer = ""

    for paragraph in paragraphs:
        if len(buffer) + len(paragraph) < MIN_CHUNK_CHARS:
            buffer = buffer + " " + paragraph if buffer else paragraph
        else:
            if buffer:
                merged.append(buffer)
            buffer = paragraph

    if buffer:
        merged.append(buffer)

    return merged


def split_long_paragraphs(paragraphs: List[str]) -> List[str]:
    result = []

    for paragraph in paragraphs:
        if len(paragraph) <= MAX_CHUNK_CHARS:
            result.append(paragraph)
        else:
            # Split at sentence boundaries where possible
            sentences = paragraph.replace(". ", ".|").split("|")
            current_chunk = ""

            for sentence in sentences:
                if len(current_chunk) + len(sentence) <= MAX_CHUNK_CHARS:
                    current_chunk = (
                        current_chunk + " " + sentence if current_chunk else sentence
                    )
                else:
                    if current_chunk:
                        result.append(current_chunk)
                    current_chunk = sentence

            if current_chunk:
                result.append(current_chunk)

    return result


def add_overlap(chunks: List[str]) -> List[str]:
    if len(chunks) <= 1:
        return chunks

    overlapped = []
    for i, chunk in enumerate(chunks):
        if i == 0:
            overlapped.append(chunk)
        else:
            # Prepend the last OVERLAP_CHARS of the previous chunk
            overlap = chunks[i - 1][-OVERLAP_CHARS:]
            overlapped.append(overlap + " " + chunk)

    return overlapped


def chunk_document(
    text: str,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    organisation_id: uuid.UUID,
) -> List[dict]:
    cleaned = clean_text(text)
    paragraphs = split_into_paragraphs(cleaned)
    paragraphs = merge_short_paragraphs(paragraphs)
    paragraphs = split_long_paragraphs(paragraphs)
    paragraphs = add_overlap(paragraphs)

    chunks = []
    for index, content in enumerate(paragraphs):
        chunks.append(
            {
                "id": uuid.uuid4(),
                "document_id": document_id,
                "user_id": user_id,
                "organisation_id": organisation_id,
                "content": content,
                "chunk_index": index,
                "token_count": len(content) // 4,  # Rough estimate: 1 token ≈ 4 chars
            }
        )

    return chunks


def chunk_document_by_pages(
    pages: List[dict],
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    organisation_id: uuid.UUID,
) -> List[dict]:
    """
    Chunk a document page by page, tagging each chunk with its page number.
    `pages` is a list of {"page_number": int|None, "text": str} from extract_pages.
    Chunk index is continuous across the whole document, not reset per page.
    """
    chunks = []
    global_index = 0

    for page in pages:
        page_number = page["page_number"]
        cleaned = clean_text(page["text"])
        paragraphs = split_into_paragraphs(cleaned)
        paragraphs = merge_short_paragraphs(paragraphs)
        paragraphs = split_long_paragraphs(paragraphs)
        paragraphs = add_overlap(paragraphs)

        for content in paragraphs:
            chunks.append(
                {
                    "id": uuid.uuid4(),
                    "document_id": document_id,
                    "user_id": user_id,
                    "organisation_id": organisation_id,
                    "content": content,
                    "chunk_index": global_index,
                    "page_number": page_number,
                    "token_count": len(content) // 4,
                }
            )
            global_index += 1

    return chunks
