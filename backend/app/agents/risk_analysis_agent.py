import asyncio
from typing import List

import anthropic
from sqlalchemy.orm import Session

from app.agents.retrieval_agent import retrieve
from app.core.circuit_breaker import anthropic_breaker
from app.core.config import get_settings
from app.services.query_classifier import QueryType
from app.services.websocket_service import manager

settings = get_settings()

GENERIC_RISK_PROMPT = """You are a risk analyst reviewing documents for a professional client.

<documents>
{context}
</documents>

<task>
Identify unusual clauses, inconsistencies, missing provisions, vague language, and one-sided terms in these documents.
</task>

<rules>
<rule>Every risk finding must include a citation in this exact format: [Document: {filename}, Page: {page}, Chunk: {chunk_index}]</rule>
<rule>Rate each finding as High, Medium, or Low severity</rule>
<rule>Be specific - quote or closely paraphrase the problematic text</rule>
<rule>If no risks found in a category, state what was checked and the confidence level</rule>
</rules>

Format each finding as:
SEVERITY: High/Medium/Low
TITLE: Short title for the risk
FINDING: What the risk is and why it matters
CITATION: [Document: ..., Page: ..., Chunk: ...]"""

LEGAL_RISK_PROMPT = """You are a legal risk analyst reviewing documents for a professional client.

<documents>
{context}
</documents>

<task>
Identify legal risks relating to: liability clauses, termination rights, IP ownership, jurisdiction, dispute resolution, change of control provisions, and indemnification obligations.
</task>

<rules>
<rule>Every risk finding must include a citation in this exact format: [Document: {filename}, Page: {page}, Chunk: {chunk_index}]</rule>
<rule>Rate each finding as High, Medium, or Low severity</rule>
<rule>Be specific - quote or closely paraphrase the problematic text</rule>
<rule>If no risks found in a category, state what was checked and the confidence level</rule>
</rules>

Format each finding as:
SEVERITY: High/Medium/Low
TITLE: Short title for the risk
FINDING: What the risk is and why it matters
CITATION: [Document: ..., Page: ..., Chunk: ...]"""

FINANCIAL_RISK_PROMPT = """You are a financial risk analyst reviewing documents for a professional client.

<documents>
{context}
</documents>

<task>
Identify financial risks relating to: calculation errors, unusual financial items, missing disclosures, contingent liabilities, covenant compliance issues, and payment terms.
</task>

<rules>
<rule>Every risk finding must include a citation in this exact format: [Document: {filename}, Page: {page}, Chunk: {chunk_index}]</rule>
<rule>Rate each finding as High, Medium, or Low severity</rule>
<rule>Be specific - quote or closely paraphrase the problematic text</rule>
<rule>If no risks found in a category, state what was checked and the confidence level</rule>
</rules>

Format each finding as:
SEVERITY: High/Medium/Low
TITLE: Short title for the risk
FINDING: What the risk is and why it matters
CITATION: [Document: ..., Page: ..., Chunk: ...]"""


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


def parse_findings(raw_output: str, agent_name: str) -> List[dict]:
    findings = []
    blocks = raw_output.strip().split("\n\n")

    for block in blocks:
        lines = block.strip().split("\n")
        finding = {
            "agent": agent_name,
            "severity": "Low",
            "title": "",
            "finding": "",
            "citation": "",
        }

        for line in lines:
            if line.startswith("SEVERITY:"):
                finding["severity"] = line.replace("SEVERITY:", "").strip()
            elif line.startswith("TITLE:"):
                finding["title"] = line.replace("TITLE:", "").strip()
            elif line.startswith("FINDING:"):
                finding["finding"] = line.replace("FINDING:", "").strip()
            elif line.startswith("CITATION:"):
                finding["citation"] = line.replace("CITATION:", "").strip()

        if finding["title"] and finding["finding"]:
            findings.append(finding)

    return findings


async def evaluate_findings(all_findings: List[dict], chunks: List[dict]) -> List[dict]:
    if not all_findings:
        return all_findings

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    findings_text = "\n\n".join(
        [
            f"AGENT: {f['agent']}\nSEVERITY: {f['severity']}\nTITLE: {f['title']}\nFINDING: {f['finding']}\nCITATION: {f['citation']}"
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
                    "3. Return the cleaned list in the same format\n"
                    "4. Keep all unique findings even if similar\n\n"
                    "Return the findings in the same SEVERITY/TITLE/FINDING/CITATION format."
                ),
            }
        ],
    )

    cleaned_text = response.content[0].text
    return parse_findings(cleaned_text, "evaluated")


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
    failed_agents = []
    for i, result in enumerate(sub_agent_results):
        if isinstance(result, Exception):
            failed_agents.append(risk_types[i])
            continue
        findings = parse_findings(result["raw_output"], result["agent"])
        all_findings.extend(findings)

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
        "chunks_analysed": len(chunks),
        "risk_types_checked": risk_types,
        "failed_agents": failed_agents,
        "total_findings": len(cleaned_findings),
    }
