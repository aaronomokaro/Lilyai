import asyncio
import re
from typing import List

import anthropic
from sqlalchemy.orm import Session

from app.agents.retrieval_agent import retrieve
from app.core.circuit_breaker import anthropic_breaker
from app.core.config import get_settings
from app.services.query_classifier import QueryType
from app.services.websocket_service import manager

settings = get_settings()

RISK_PROMPT_TEMPLATE = """You are a {role} reviewing documents for a professional client.

<documents>
{context}
</documents>

<task>
{task}
</task>

<rules>
<rule id="1">Every risk finding must include a citation in this exact format: [Document: {{filename}}, Page: {{page}}, Chunk: {{chunk_index}}]</rule>
<rule id="2">Rate each finding as High, Medium, or Low severity based on potential impact to the client, not likelihood alone.</rule>
<rule id="3">Be specific. Quote or closely paraphrase the problematic text. Do not describe risks in general terms.</rule>
<rule id="4">Distinguish standard boilerplate from genuine risk. Standard limitation of liability clauses, standard notice periods, and standard confidentiality terms are not risks unless they deviate materially from typical market terms or create clear one-sided exposure.</rule>
<rule id="5">For each category checked, report one of three outcomes: a finding, no risk identified with confidence stated, or cannot be assessed if the documents lack the information needed to evaluate that category.</rule>
<rule id="6">Produce as many findings as the documents genuinely support. Do not pad with minor observations to appear thorough. Do not omit findings to appear concise.</rule>
</rules>

<output_format>
Return each finding using this structure:

<finding>
<severity>High|Medium|Low</severity>
<title>Short title for the risk</title>
<description>What the risk is and why it matters to the client</description>
<citation>[Document: filename, Page: page_number, Chunk: chunk_index]</citation>
</finding>

For categories with no risk found:
<checked>
<category>category name</category>
<result>no_risk_identified|cannot_be_assessed</result>
<note>Brief statement of what was checked or why it could not be assessed</note>
</checked>
</output_format>

<example>
<finding>
<severity>High</severity>
<title>Uncapped indemnification obligation</title>
<description>The indemnification clause requires the client to indemnify the counterparty for all losses without any cap on liability, exposing the client to potentially unlimited financial risk.</description>
<citation>[Document: services_agreement.pdf, Page: 8, Chunk: 5]</citation>
</finding>

<checked>
<category>jurisdiction and dispute resolution</category>
<result>no_risk_identified</result>
<note>Governing law and jurisdiction clauses are standard and mutually agreed. Dispute resolution follows a conventional arbitration process.</note>
</checked>
</example>"""


GENERIC_RISK_TASK = """Identify unusual clauses, inconsistencies, missing provisions, vague language, and one-sided terms in these documents."""

LEGAL_RISK_TASK = """Identify legal risks relating to: liability clauses, termination rights, IP ownership, jurisdiction, dispute resolution, change of control provisions, and indemnification obligations."""

FINANCIAL_RISK_TASK = """Identify financial risks relating to: calculation errors, unusual financial items, missing disclosures, contingent liabilities, covenant compliance issues, and payment terms."""

GENERIC_RISK_PROMPT = RISK_PROMPT_TEMPLATE.format(
    role="risk analyst",
    task=GENERIC_RISK_TASK,
    context="{context}",
    filename="{filename}",
    page="{page}",
    chunk_index="{chunk_index}",
)
LEGAL_RISK_PROMPT = RISK_PROMPT_TEMPLATE.format(
    role="legal risk analyst",
    task=LEGAL_RISK_TASK,
    context="{context}",
    filename="{filename}",
    page="{page}",
    chunk_index="{chunk_index}",
)
FINANCIAL_RISK_PROMPT = RISK_PROMPT_TEMPLATE.format(
    role="financial risk analyst",
    task=FINANCIAL_RISK_TASK,
    context="{context}",
    filename="{filename}",
    page="{page}",
    chunk_index="{chunk_index}",
)


def build_context_from_chunks(chunks: List[dict]) -> str:
    parts = []
    for chunk in chunks:
        parts.append(
            f"<chunk>\n"
            f"<filename>{chunk.get('filename', 'Unknown')}</filename>\n"
            f"<page>{chunk.get('page_number', 'Unknown')}</page>\n"
            f"<chunk_index>{chunk['chunk_index']}</chunk_index>\n"
            f"<content>{chunk['content']}</content>\n"
            f"</chunk>"
        )
    return "\n\n".join(parts)


async def run_sub_agent(
    prompt_template: str,
    chunks: List[dict],
    agent_name: str,
) -> dict:
    context = build_context_from_chunks(chunks)
    filled_prompt = prompt_template.format(
        context=context,
        filename="{filename}",
        page="{page}",
        chunk_index="{chunk_index}",
    )

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def _call():
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[{"role": "user", "content": filled_prompt}],
        )
        return response.content[0].text

    raw_output = await anthropic_breaker.call(_call)

    return {
        "agent": agent_name,
        "raw_output": raw_output,
        "chunks_used": [c["chunk_id"] for c in chunks],
    }


def parse_findings(raw_output: str, agent_name: str) -> tuple[List[dict], List[dict]]:
    findings = []

    finding_blocks = re.findall(r"<finding>(.*?)</finding>", raw_output, re.DOTALL)

    for block in finding_blocks:
        severity_match = re.search(r"<severity>(.*?)</severity>", block, re.DOTALL)
        title_match = re.search(r"<title>(.*?)</title>", block, re.DOTALL)
        description_match = re.search(
            r"<description>(.*?)</description>", block, re.DOTALL
        )
        citation_match = re.search(r"<citation>(.*?)</citation>", block, re.DOTALL)
        finding = {
            "agent": agent_name,
            "severity": severity_match.group(1).strip() if severity_match else "Low",
            "title": title_match.group(1).strip() if title_match else "",
            "finding": description_match.group(1).strip() if description_match else "",
            "citation": citation_match.group(1).strip() if citation_match else "",
        }
        if finding["title"] and finding["finding"]:
            findings.append(finding)

    checked_blocks = re.findall(r"<checked>(.*?)</checked>", raw_output, re.DOTALL)
    checked_categories = []

    for block in checked_blocks:
        category_match = re.search(r"<category>(.*?)</category>", block, re.DOTALL)
        result_match = re.search(r"<result>(.*?)</result>", block, re.DOTALL)
        note_match = re.search(r"<note>(.*?)</note>", block, re.DOTALL)

        checked_categories.append(
            {
                "agent": agent_name,
                "category": category_match.group(1).strip() if category_match else "",
                "result": result_match.group(1).strip() if result_match else "",
                "note": note_match.group(1).strip() if note_match else "",
            }
        )

    return findings, checked_categories


async def evaluate_findings(all_findings: List[dict], chunks: List[dict]) -> List[dict]:
    if not all_findings:
        return all_findings

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    findings_text = "\n\n".join(
        [
            f"<finding>\n<agent>{f['agent']}</agent>\n<severity>{f['severity']}</severity>\n"
            f"<title>{f['title']}</title>\n<description>{f['finding']}</description>\n"
            f"<citation>{f['citation']}</citation>\n</finding>"
            for f in all_findings
        ]
    )

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    f"<findings>\n{findings_text}\n</findings>\n\n"
                    "Review these risk findings and:\n"
                    "1. Remove exact duplicates - same risk identified by multiple agents\n"
                    "2. Verify each finding has a valid citation\n"
                    "3. Keep all unique findings even if similar\n\n"
                    "Return the cleaned findings using this exact format for each:\n\n"
                    "<finding>\n<severity>High|Medium|Low</severity>\n<title>Short title</title>\n"
                    "<description>What the risk is and why it matters</description>\n"
                    "<citation>[Document: filename, Page: page, Chunk: chunk_index]</citation>\n</finding>"
                ),
            }
        ],
    )

    cleaned_text = response.content[0].text
    deduplicated_findings, _ = parse_findings(cleaned_text, "evaluated")
    return deduplicated_findings


async def analyse_risks(
    request: str,
    user_id: str,
    organisation_id: str,
    document_ids: List[str],
    db: Session,
    risk_types: List[str] = None,
) -> dict:
    if risk_types is None:
        risk_types = ["generic", "legal", "financial"]

    # Retrieve chunks for risk analysis - use high top_k
    chunks, trajectory, was_successful = await retrieve(
        question=request if request else "identify all risks in these documents",
        query_type=QueryType.RISK,
        user_id=user_id,
        organisation_id=organisation_id,
        top_k=12,
        document_ids=document_ids,
    )

    # Enrich chunks with metadata
    from app.services.query_service import get_chunk_metadata, get_document_filenames

    chunk_ids = [c["chunk_id"] for c in chunks]
    document_id_list = list(set([c["document_id"] for c in chunks]))
    chunk_metadata = get_chunk_metadata(chunk_ids, db)
    doc_filenames = get_document_filenames(document_id_list, db)

    for chunk in chunks:
        meta = chunk_metadata.get(chunk["chunk_id"], {})
        chunk["page_number"] = meta.get("page_number")
        chunk["filename"] = doc_filenames.get(chunk["document_id"], "Unknown")

    # Run sub-agents in parallel
    tasks = []
    if "generic" in risk_types:
        tasks.append(run_sub_agent(GENERIC_RISK_PROMPT, chunks, "generic"))
    if "legal" in risk_types:
        tasks.append(run_sub_agent(LEGAL_RISK_PROMPT, chunks, "legal"))
    if "financial" in risk_types:
        tasks.append(run_sub_agent(FINANCIAL_RISK_PROMPT, chunks, "financial"))

    sub_agent_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Parse findings from all sub-agents
    all_findings = []
    all_checked_categories = []
    failed_agents = []
    for i, result in enumerate(sub_agent_results):
        if isinstance(result, Exception):
            failed_agents.append(risk_types[i])
            continue
        findings, checked_categories = parse_findings(
            result["raw_output"], result["agent"]
        )
        all_findings.extend(findings)
        all_checked_categories.extend(checked_categories)

    # Evaluate and deduplicate findings
    if all_findings:
        cleaned_findings = await evaluate_findings(all_findings, chunks)
        # Sort by severity - High first
        severity_order = {"High": 0, "Medium": 1, "Low": 2}
        cleaned_findings.sort(
            key=lambda x: severity_order.get(x.get("severity", "Low"), 2)
        )
    else:
        cleaned_findings = []

    return {
        "findings": cleaned_findings,
        "checked_categories": all_checked_categories,
        "chunks_analysed": len(chunks),
        "risk_types_checked": risk_types,
        "failed_agents": failed_agents,
        "total_findings": len(cleaned_findings),
    }
