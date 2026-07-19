import logging
import re
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
logger = logging.getLogger(__name__)

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

OUTPUT_PROMPT = """<role>You are a professional document formatter for a document intelligence platform serving legal and finance professionals. You format findings into structured professional documents. You never add information beyond what is in the source material.</role>

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
<rule id="9">Length should match the content, not a target word count. A report with 3 supported findings should be short. Do not pad to appear thorough.</rule>
<rule id="10">If the source material is too thin to produce a meaningful {output_type_label}, state this directly at the top: "There is insufficient source material to produce a complete {output_type_label}. The following is based on the limited content available:" and proceed with whatever can be honestly supported.</rule>
</rules>

<task>Format the source material into a professional {output_type_label}. Structure it clearly and ensure every claim retains its citation.</task>

<example>
Executive Summary: This due diligence summary covers three key areas of the target company's commercial agreements, identifying one high-priority liability concern and two areas requiring further review.

Key Contractual Obligations: The primary services agreement includes an uncapped indemnification clause exposing the acquirer to potentially unlimited liability. [Document: services_agreement.pdf, Page: 8, Chunk: 5]

Key Findings: The uncapped indemnification clause should be renegotiated before close. [Document: services_agreement.pdf, Page: 8, Chunk: 5]
</example>"""

OUTPUT_TYPE_CLASSIFICATION_PROMPT = """You are classifying what type of formatted output a user wants from a document intelligence platform.

<request>{request}</request>

<output_types>
<type id="contract_risk_report">User wants a report specifically on risks in a contract or agreement.</type>
<type id="due_diligence_summary">User wants a due diligence style summary covering multiple areas of a deal or document set.</type>
<type id="clause_extraction_table">User wants specific clauses or fields pulled out into a table or list format.</type>
<type id="data_aggregation_table">User wants data points from multiple documents pulled into one table.</type>
<type id="version_comparison_report">User wants a report showing what changed between document versions.</type>
<type id="reference_list">User wants a bibliography or reference list.</type>
<type id="executive_briefing">General summary request that does not fit any category above.</type>
</output_types>

Respond in this exact format:
<output_type>type_id</output_type>
<confidence>high|medium|low</confidence>"""


def detect_output_type(request: str) -> Optional[str]:
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
    if any(
        w in request_lower
        for w in ["executive briefing", "summary", "brief", "overview"]
    ):
        return "executive_briefing"

    return None


async def detect_output_type_with_fallback(request: str) -> str:
    rule_based_result = detect_output_type(request)
    if rule_based_result:
        return rule_based_result

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=50,
        messages=[
            {
                "role": "user",
                "content": OUTPUT_TYPE_CLASSIFICATION_PROMPT.format(request=request),
            }
        ],
    )
    raw_text = response.content[0].text.strip()

    type_match = re.search(r"<output_type>(.*?)</output_type>", raw_text)
    confidence_match = re.search(r"<confidence>(.*?)</confidence>", raw_text)

    output_type = type_match.group(1).strip() if type_match else "executive_briefing"
    confidence = (
        confidence_match.group(1).strip().lower() if confidence_match else "low"
    )

    if confidence == "low":
        logger.warning(
            f"Low confidence output type classification: type={output_type}, request={request[:100]}"
        )

    return output_type


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
    output_type = await detect_output_type_with_fallback(request)

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
