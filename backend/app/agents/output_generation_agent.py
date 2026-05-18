import uuid
from typing import List, Optional

import anthropic
from sqlalchemy.orm import Session

from app.core.circuit_breaker import anthropic_breaker
from app.core.config import get_settings
from app.models.output import Output
from app.services.s3_service import build_s3_key, upload_document
from app.services.websocket_service import manager

settings = get_settings()

OUTPUT_TYPES = {
    "contract_risk_report": "Contract Risk Report",
    "due_diligence_summary": "Due Diligence Summary",
    "clause_extraction_table": "Clause Extraction Table",
    "data_aggregation_table": "Data Aggregation Table",
    "version_comparison_report": "Version Comparison Report",
    "reference_list": "Reference List",
    "executive_briefing": "Executive Briefing",
}

STORAGE_PERMANENT_TIERS = ["professional", "enterprise"]

OUTPUT_PROMPT = """<role>You are a professional document formatter for a document intelligence platform. You format findings into structured professional documents. You never add information beyond what is in the source material.</role>

<output_type>{output_type}</output_type>

<output_type_label>{output_type_label}</output_type_label>

<source_material>
{source_material}
</source_material>

<rules>
<rule id="1">Start with an executive summary of 2-3 sentences maximum.</rule>
<rule id="2">Use clear section headings followed by a colon. No markdown symbols like ** or ##.</rule>
<rule id="3">Every claim must retain its original citation in this exact format: [Document: filename, Page: N, Chunk: N]. Never remove or alter citations.</rule>
<rule id="4">Use professional language appropriate for legal and financial professionals.</rule>
<rule id="5">Core sections must always be present. Optional sections only if relevant content exists in the source material.</rule>
<rule id="6">End with a key findings or conclusions section.</rule>
<rule id="7">Return clean plain text only. No markdown formatting symbols.</rule>
<rule id="8">Never add information, opinions, or claims not present in the source material.</rule>
</rules>

<task>Format the source material into a professional {output_type_label}. Structure it clearly and ensure every claim retains its citation.</task>"""


def detect_output_type(request: str) -> str:
    request_lower = request.lower()

    if any(
        w in request_lower
        for w in ["risk report", "risk analysis report", "contract risk"]
    ):
        return "contract_risk_report"
    if any(w in request_lower for w in ["due diligence", "dd report", "due dil"]):
        return "due_diligence_summary"
    if any(w in request_lower for w in ["clause", "extract clauses", "clause table"]):
        return "clause_extraction_table"
    if any(w in request_lower for w in ["aggregate", "data table", "aggregation"]):
        return "data_aggregation_table"
    if any(w in request_lower for w in ["compare", "version comparison", "changes"]):
        return "version_comparison_report"
    if any(w in request_lower for w in ["reference", "bibliography", "apa", "harvard"]):
        return "reference_list"

    return "executive_briefing"


async def format_output(
    output_type: str,
    source_material: str,
) -> str:
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    output_type_label = OUTPUT_TYPES.get(output_type, "Executive Briefing")

    filled_prompt = OUTPUT_PROMPT.format(
        output_type=output_type,
        output_type_label=output_type_label,
        source_material=source_material,
    )

    async def _call():
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": filled_prompt}],
        )
        return response.content[0].text

    return await anthropic_breaker.call(_call)


async def store_output(
    formatted_content: str,
    output_type: str,
    user_id: str,
    organisation_id: Optional[str],
    tier: str,
    db: Session,
) -> dict:
    output_id = uuid.uuid4()
    org_id = organisation_id if organisation_id else user_id
    s3_key = build_s3_key(
        org_id=org_id,
        user_id=user_id,
        doc_id=str(output_id),
        filename=f"{output_type}_{output_id}.txt",
    )

    await upload_document(
        file_content=formatted_content.encode("utf-8"),
        s3_key=s3_key,
        content_type="text/plain",
    )

    is_permanent = tier in STORAGE_PERMANENT_TIERS

    import datetime

    expires_at = None
    if not is_permanent:
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=24)

    from uuid import UUID

    output_record = Output(
        id=output_id,
        user_id=UUID(user_id),
        organisation_id=UUID(organisation_id) if organisation_id else None,
        output_type=output_type,
        format="txt",
        s3_key=s3_key,
        status="ready",
        is_permanent=is_permanent,
        expires_at=expires_at,
        output_metadata={"output_type_label": OUTPUT_TYPES.get(output_type, "Report")},
    )
    db.add(output_record)
    db.commit()

    return {
        "output_id": str(output_id),
        "output_type": output_type,
        "output_type_label": OUTPUT_TYPES.get(output_type, "Report"),
        "s3_key": s3_key,
        "is_permanent": is_permanent,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }


async def generate_output(
    request: str,
    user_id: str,
    organisation_id: Optional[str],
    document_ids: List[str],
    db: Session,
    tier: str = "starter",
    source_material: Optional[str] = None,
) -> dict:
    output_type = detect_output_type(request)

    await manager.send_to_user(
        user_id=user_id,
        message={
            "event": "output_progress",
            "step": "formatting",
            "output_type": output_type,
        },
    )

    if not source_material:
        from app.agents.retrieval_agent import retrieve
        from app.services.query_classifier import QueryType
        from app.services.query_service import (
            get_chunk_metadata,
            get_document_filenames,
        )

        chunks, _, _ = await retrieve(
            question=request,
            query_type=QueryType.CONCEPTUAL,
            user_id=user_id,
            organisation_id=organisation_id,
            top_k=8,
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

        source_material = "\n\n".join(
            [
                f"<source_chunk>\n"
                f"<filename>{c.get('filename', 'Unknown')}</filename>\n"
                f"<page>{c.get('page_number', 'N/A')}</page>\n"
                f"<content>{c['content']}</content>\n"
                f"</source_chunk>"
                for c in chunks
            ]
        )

    formatted_content = await format_output(output_type, source_material)

    output_info = await store_output(
        formatted_content=formatted_content,
        output_type=output_type,
        user_id=user_id,
        organisation_id=organisation_id,
        tier=tier,
        db=db,
    )

    await manager.send_to_user(
        user_id=user_id,
        message={
            "event": "output_ready",
            "output_id": output_info["output_id"],
            "output_type_label": output_info["output_type_label"],
            "is_permanent": output_info["is_permanent"],
            "expires_at": output_info["expires_at"],
        },
    )

    return output_info
