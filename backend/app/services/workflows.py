from typing import List, Optional

import anthropic
from sqlalchemy.orm import Session

from app.agents.retrieval_agent import retrieve
from app.core.circuit_breaker import anthropic_breaker
from app.core.config import get_settings
from app.services.query_classifier import QueryType
from app.services.query_service import get_chunk_metadata, get_document_filenames

settings = get_settings()

REFERENCE_LIST_PROMPT = """<role>You are a professional academic reference formatter. You create accurate bibliographies from document metadata.</role>

<documents>
{documents}
</documents>

<style>{style}</style>

<example>
<input>filename: Smith_Contract_Analysis_2024.pdf, doc_type: report, uploaded_at: 2024-03-15</input>
<output_harvard>Smith, J. (2024) Contract Analysis Report. London: LilyAI Platform. Available at: Smith_Contract_Analysis_2024.pdf (Accessed: 15 March 2024).</output_harvard>
<output_apa>Smith, J. (2024). Contract analysis report. LilyAI Platform.</output_apa>
</example>

<rules>
<rule id="1">Format every document as a proper reference in the requested citation style.</rule>
<rule id="2">Extract author, title, date, publisher, and any other relevant metadata from the document content.</rule>
<rule id="3">If a metadata field cannot be found, use the filename as the title and mark other fields as unknown.</rule>
<rule id="4">Sort references alphabetically by author surname.</rule>
<rule id="5">Return only the formatted reference list. No commentary.</rule>
</rules>

<task>Generate a {style} reference list from the provided documents.</task>"""

REVIEW_EXTRACTION_PROMPT = """<role>You are a professional document analyst specialising in systematic clause and field extraction.</role>

<documents>
{context}
</documents>

<extraction_request>{request}</extraction_request>

<example>
<input>Extract all notice periods</input>
<output>
FIELD: Notice Period
VALUE: 30 days written notice required for termination by either party
CITATION: [Document: employment_contract.pdf, Page: 4, Chunk: 2]

FIELD: Notice Period
VALUE: 14 days notice required for breach remedy
CITATION: [Document: employment_contract.pdf, Page: 7, Chunk: 5]
</output>
</example>

<rules>
<rule id="1">Extract every instance of the requested clause or field.</rule>
<rule id="2">Every extraction must include a citation: [Document: filename, Page: N, Chunk: N]</rule>
<rule id="3">Present extractions in a structured format: field name, extracted value, citation.</rule>
<rule id="4">If a field is not found, explicitly state it is absent.</rule>
<rule id="5">Do not interpret or summarise - extract the exact text.</rule>
</rules>

<task>Systematically extract all instances of: {request}</task>"""

VERSION_COMPARISON_PROMPT = """<role>You are a professional document analyst specialising in version comparison and change identification.</role>

<document_version_1>
{version_1}
</document_version_1>

<document_version_2>
{version_2}
</document_version_2>

<example>
<input>Version 1: "The notice period shall be 30 days." Version 2: "The notice period shall be 7 days."</input>
<output>
SEVERITY: Critical
CHANGE: Notice period reduced from 30 days to 7 days
IMPACT: Significantly reduces time available to respond to termination notices
CITATION V1: [Document: contract_v1.pdf, Page: 5, Chunk: 3]
CITATION V2: [Document: contract_v2.pdf, Page: 5, Chunk: 3]
</output>
</example>

<rules>
<rule id="1">Identify every change between version 1 and version 2.</rule>
<rule id="2">Rate each change as: Critical, Significant, Minor, or Administrative.</rule>
<rule id="3">Every change must include citations from both versions where applicable.</rule>
<rule id="4">Critical: changes that materially affect rights, obligations, or risk.</rule>
<rule id="5">Significant: changes that alter meaning but not core obligations.</rule>
<rule id="6">Minor: changes that clarify without altering meaning.</rule>
<rule id="7">Administrative: formatting, numbering, or typographical changes.</rule>
</rules>

<task>Compare the two document versions and identify all changes with significance ratings.</task>"""

DATA_AGGREGATION_PROMPT = """<role>You are a professional data analyst specialising in cross-document data extraction and aggregation.</role>

<documents>
{context}
</documents>

<aggregation_request>{request}</aggregation_request>

<example>
<input>Extract payment terms from all contracts</input>
<output>
Document: contract_acme.pdf | Data Point: Payment Terms | Value: Net 30 days from invoice date | Citation: [Document: contract_acme.pdf, Page: 3, Chunk: 2]
Document: contract_techcorp.pdf | Data Point: Payment Terms | Value: Net 60 days from invoice date | Citation: [Document: contract_techcorp.pdf, Page: 4, Chunk: 1]
Document: contract_finco.pdf | Data Point: Payment Terms | Value: Not Found
</output>
</example>

<rules>
<rule id="1">Extract the requested data points from every document.</rule>
<rule id="2">Present results in a structured table format: Document | Data Point | Value | Citation.</rule>
<rule id="3">Every value must include a citation: [Document: filename, Page: N, Chunk: N]</rule>
<rule id="4">If a data point is not found in a document, mark it as Not Found.</rule>
<rule id="5">Be precise - extract exact values, not summaries.</rule>
<rule id="6">Maintain consistency in how values are presented across documents.</rule>
</rules>

<task>Aggregate the following data points across all provided documents: {request}</task>"""


async def run_review_extraction(
    request: str,
    user_id: str,
    organisation_id: Optional[str],
    document_ids: List[str],
    db: Session,
) -> dict:
    chunks, trajectory, was_successful = await retrieve(
        question=request,
        query_type=QueryType.MIXED,
        user_id=user_id,
        organisation_id=organisation_id,
        top_k=10,
        document_ids=document_ids,
    )

    chunk_ids = [c["chunk_id"] for c in chunks]
    document_id_list = list(set([c["document_id"] for c in chunks]))
    chunk_metadata = get_chunk_metadata(chunk_ids, db)
    doc_filenames = get_document_filenames(document_id_list, db)

    for chunk in chunks:
        meta = chunk_metadata.get(chunk["chunk_id"], {})
        chunk["page_number"] = meta.get("page_number")
        chunk["filename"] = doc_filenames.get(chunk["document_id"], "Unknown")

    context = "\n\n".join(
        [
            f"<chunk>\n"
            f"<filename>{c.get('filename', 'Unknown')}</filename>\n"
            f"<page>{c.get('page_number', 'N/A')}</page>\n"
            f"<chunk_index>{c['chunk_index']}</chunk_index>\n"
            f"<content>{c['content']}</content>\n"
            f"</chunk>"
            for c in chunks
        ]
    )

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def _call():
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": REVIEW_EXTRACTION_PROMPT.format(
                        context=context,
                        request=request,
                    ),
                }
            ],
        )
        return response.content[0].text

    result = await anthropic_breaker.call(_call)
    return {
        "workflow": "review_extraction",
        "result": result,
        "chunks_used": len(chunks),
    }


async def run_version_comparison(
    request: str,
    user_id: str,
    organisation_id: Optional[str],
    document_ids: List[str],
    db: Session,
) -> dict:
    if len(document_ids) < 2:
        return {
            "workflow": "version_comparison",
            "error": "Version comparison requires exactly two documents. Please specify two document IDs.",
        }

    # Retrieve chunks from each version separately
    v1_chunks, _, _ = await retrieve(
        question=request if request else "full document content",
        query_type=QueryType.MIXED,
        user_id=user_id,
        organisation_id=organisation_id,
        top_k=10,
        document_ids=[document_ids[0]],
    )

    v2_chunks, _, _ = await retrieve(
        question=request if request else "full document content",
        query_type=QueryType.MIXED,
        user_id=user_id,
        organisation_id=organisation_id,
        top_k=10,
        document_ids=[document_ids[1]],
    )

    def format_chunks(chunks):
        return "\n\n".join(
            [
                f"<chunk>\n<page>{c.get('page_number', 'N/A')}</page>\n"
                f"<chunk_index>{c['chunk_index']}</chunk_index>\n"
                f"<content>{c['content']}</content>\n</chunk>"
                for c in chunks
            ]
        )

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def _call():
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": VERSION_COMPARISON_PROMPT.format(
                        version_1=format_chunks(v1_chunks),
                        version_2=format_chunks(v2_chunks),
                    ),
                }
            ],
        )
        return response.content[0].text

    result = await anthropic_breaker.call(_call)
    return {"workflow": "version_comparison", "result": result}


async def run_data_aggregation(
    request: str,
    user_id: str,
    organisation_id: Optional[str],
    document_ids: List[str],
    db: Session,
) -> dict:
    chunks, trajectory, was_successful = await retrieve(
        question=request,
        query_type=QueryType.CROSS_DOC,
        user_id=user_id,
        organisation_id=organisation_id,
        top_k=12,
        document_ids=document_ids,
    )

    chunk_ids = [c["chunk_id"] for c in chunks]
    document_id_list = list(set([c["document_id"] for c in chunks]))
    chunk_metadata = get_chunk_metadata(chunk_ids, db)
    doc_filenames = get_document_filenames(document_id_list, db)

    for chunk in chunks:
        meta = chunk_metadata.get(chunk["chunk_id"], {})
        chunk["page_number"] = meta.get("page_number")
        chunk["filename"] = doc_filenames.get(chunk["document_id"], "Unknown")

    context = "\n\n".join(
        [
            f"<chunk>\n"
            f"<filename>{c.get('filename', 'Unknown')}</filename>\n"
            f"<page>{c.get('page_number', 'N/A')}</page>\n"
            f"<chunk_index>{c['chunk_index']}</chunk_index>\n"
            f"<content>{c['content']}</content>\n"
            f"</chunk>"
            for c in chunks
        ]
    )

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def _call():
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": DATA_AGGREGATION_PROMPT.format(
                        context=context,
                        request=request,
                    ),
                }
            ],
        )
        return response.content[0].text

    result = await anthropic_breaker.call(_call)
    return {
        "workflow": "data_aggregation",
        "result": result,
        "chunks_used": len(chunks),
    }


async def run_reference_list(
    user_id: str,
    organisation_id: Optional[str],
    document_ids: List[str],
    db: Session,
    style: str = "Harvard",
) -> dict:
    from uuid import UUID

    from app.models.document import Document

    documents = (
        db.query(Document)
        .filter(
            Document.id.in_([UUID(did) for did in document_ids]),
            Document.user_id == UUID(user_id),
            Document.is_active == True,
        )
        .all()
    )

    if not documents:
        return {"workflow": "reference_list", "error": "No documents found."}

    doc_list = "\n".join(
        [
            f"<document>\n"
            f"<filename>{doc.filename}</filename>\n"
            f"<doc_type>{doc.doc_type or 'Unknown'}</doc_type>\n"
            f"<uploaded_at>{doc.created_at.isoformat()}</uploaded_at>\n"
            f"</document>"
            for doc in documents
        ]
    )

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def _call():
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": REFERENCE_LIST_PROMPT.format(
                        documents=doc_list,
                        style=style,
                    ),
                }
            ],
        )
        return response.content[0].text

    result = await anthropic_breaker.call(_call)
    return {"workflow": "reference_list", "style": style, "result": result}
