import asyncio
import logging
import re
from typing import Any

import anthropic

from app.core.config import get_settings
from app.services.websocket_service import manager

settings = get_settings()
logger = logging.getLogger(__name__)

INTENT_CLASSIFICATION_PROMPT = """You are classifying a user request for a document intelligence platform serving legal and finance professionals.

<request>{request}</request>

<categories>
<category id="query">User is asking a factual question about document content. Example: "What is the notice period in this contract?"</category>
<category id="risk_analysis">User wants risks, issues, or red flags identified. Example: "What risks are in this agreement?" or "Flag any concerns in this document."</category>
<category id="extract_clauses">User wants specific clauses, fields, or sections extracted. Example: "Pull out all the payment terms" or "List the termination clauses."</category>
<category id="compare_versions">User wants two versions of a document compared. Example: "What changed between version 1 and version 2?"</category>
<category id="aggregate_data">User wants data points pulled across multiple documents. Example: "What are the total contract values across all these agreements?"</category>
<category id="generate_output">User wants a structured report or summary generated. Example: "Generate a summary report of this document."</category>
<category id="send_email">User wants to send content via Gmail. Example: "Email this summary to my client."</category>
<category id="save_to_drive">User wants to save content to Google Drive. Example: "Save this to my Drive."</category>
<category id="generate_references">User wants a reference list or bibliography. Example: "Generate a reference list from these research papers."</category>
<category id="unknown">Request does not clearly fit any category above.</category>
</categories>

<rules>
<rule id="1">Classify into exactly one category.</rule>
<rule id="2">If the request is ambiguous between query and risk_analysis, choose risk_analysis only if the user explicitly mentions risks, flags, concerns, or issues.</rule>
<rule id="3">If uncertain between two categories, choose the simpler one. query is simpler than risk_analysis. extract_clauses is simpler than aggregate_data.</rule>
<rule id="4">Use unknown only if the request genuinely does not fit any category.</rule>
</rules>

Respond in this exact format:
<intent>category_name</intent>
<confidence>high|medium|low</confidence>
<reason>one sentence explaining the classification</reason>"""


async def classify_intent(request: str) -> str:
    # Rule-based first - fast and free
    request_lower = request.lower()

    risk_signals = [
        "risk",
        "risks",
        "liability",
        "flag",
        "unusual",
        "concern",
        "analyse risks",
        "analyze risks",
    ]
    for signal in risk_signals:
        if signal in request_lower:
            return "risk_analysis"

    compare_signals = ["compare", "difference between", "changes between", "version"]
    for signal in compare_signals:
        if signal in request_lower:
            return "compare_versions"

    extract_signals = [
        "extract",
        "list all",
        "pull out",
        "find all clauses",
        "find all fields",
    ]
    for signal in extract_signals:
        if signal in request_lower:
            return "extract_clauses"

    aggregate_signals = [
        "aggregate",
        "across all documents",
        "summarise all",
        "summarize all",
        "table of",
    ]
    for signal in aggregate_signals:
        if signal in request_lower:
            return "aggregate_data"

    output_signals = [
        "generate report",
        "create report",
        "write a summary",
        "due diligence report",
        "executive briefing",
    ]
    for signal in output_signals:
        if signal in request_lower:
            return "generate_output"

    email_signals = ["send via email", "send via gmail", "email this", "email the"]
    for signal in email_signals:
        if signal in request_lower:
            return "send_email"

    drive_signals = ["save to drive", "save to google drive", "upload to drive"]
    for signal in drive_signals:
        if signal in request_lower:
            return "save_to_drive"

    reference_signals = [
        "reference list",
        "bibliography",
        "apa",
        "harvard referencing",
        "citations list",
    ]
    for signal in reference_signals:
        if signal in request_lower:
            return "generate_references"

    # Uncertain - escalate to Haiku
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        messages=[
            {
                "role": "user",
                "content": INTENT_CLASSIFICATION_PROMPT.format(request=request),
            }
        ],
    )
    raw_text = response.content[0].text.strip()

    intent_match = re.search(r"<intent>(.*?)</intent>", raw_text)
    confidence_match = re.search(r"<confidence>(.*?)</confidence>", raw_text)
    reason_match = re.search(r"<reason>(.*?)</reason>", raw_text)
    intent = intent_match.group(1).strip().lower() if intent_match else "unknown"
    confidence = (
        confidence_match.group(1).strip().lower() if confidence_match else "low"
    )
    reason = reason_match.group(1).strip() if reason_match else "No reason provided"

    if confidence == "low":
        logger.warning(
            f"low confidence intent classification: intent={intent}, "
            f"reason={reason}, request={request[:100]}"
        )

    return intent


async def requires_confirmation(intent: str) -> bool:
    # Irreversible actions require explicit user confirmation
    return intent in ["send_email", "save_to_drive"]


async def orchestrate(
    request: str,
    user_id: str,
    conversation_id: str,
    organisation_id: str,
    tier: str,
    document_ids: list,
    db,
) -> dict:
    intent = await classify_intent(request)

    # Notify frontend of progress
    await manager.send_to_user(
        user_id=user_id,
        message={
            "event": "orchestrator_progress",
            "step": "classified",
            "intent": intent,
        },
    )

    # Confirmation required for irreversible actions
    if await requires_confirmation(intent):
        return {
            "requires_confirmation": True,
            "intent": intent,
            "message": f"This will {intent.replace('_', ' ')}. Please confirm.",
        }

    # Route to the correct workflow or agent
    if intent == "query":
        return await _run_query_workflow(
            request=request,
            user_id=user_id,
            conversation_id=conversation_id,
            organisation_id=organisation_id,
            tier=tier,
            document_ids=document_ids,
            db=db,
        )

    elif intent == "risk_analysis":
        return await _run_risk_workflow(
            request=request,
            user_id=user_id,
            conversation_id=conversation_id,
            organisation_id=organisation_id,
            document_ids=document_ids,
            db=db,
        )

    elif intent == "generate_output":
        return await _run_output_workflow(
            request=request,
            user_id=user_id,
            conversation_id=conversation_id,
            organisation_id=organisation_id,
            document_ids=document_ids,
            db=db,
        )

    elif intent == "extract_clauses":
        return await _run_extraction_workflow(
            request=request,
            user_id=user_id,
            conversation_id=conversation_id,
            organisation_id=organisation_id,
            document_ids=document_ids,
            db=db,
        )

    elif intent == "compare_versions":
        return await _run_comparison_workflow(
            request=request,
            user_id=user_id,
            conversation_id=conversation_id,
            organisation_id=organisation_id,
            document_ids=document_ids,
            db=db,
        )

    elif intent == "aggregate_data":
        return await _run_aggregation_workflow(
            request=request,
            user_id=user_id,
            conversation_id=conversation_id,
            organisation_id=organisation_id,
            document_ids=document_ids,
            db=db,
        )

    elif intent == "generate_references":
        return await _run_reference_workflow(
            request=request,
            user_id=user_id,
            conversation_id=conversation_id,
            organisation_id=organisation_id,
            document_ids=document_ids,
            db=db,
        )

    else:
        # unknown or unhandled intent - treat as a query
        return await _run_query_workflow(
            request=request,
            user_id=user_id,
            conversation_id=conversation_id,
            organisation_id=organisation_id,
            tier=tier,
            document_ids=document_ids,
            db=db,
        )


async def _run_query_workflow(
    request, user_id, conversation_id, organisation_id, tier, document_ids, db
):
    from uuid import UUID

    from app.services.query_service import process_query

    await manager.send_to_user(
        user_id=user_id,
        message={"event": "orchestrator_progress", "step": "running_query"},
    )

    tokens = []
    async for token in process_query(
        question=request,
        conversation_id=UUID(conversation_id),
        user_id=UUID(user_id),
        organisation_id=UUID(organisation_id) if organisation_id else None,
        tier=tier,
        db=db,
        document_ids=document_ids,
    ):
        tokens.append(token)

    return {"intent": "query", "status": "completed"}


async def _run_risk_workflow(
    request, user_id, conversation_id, organisation_id, document_ids, db
):
    from app.agents.risk_analysis_agent import analyse_risks

    await manager.send_to_user(
        user_id=user_id,
        message={"event": "orchestrator_progress", "step": "running_risk_analysis"},
    )

    result = await analyse_risks(
        request=request,
        user_id=user_id,
        organisation_id=organisation_id,
        document_ids=document_ids,
        db=db,
    )

    return {"intent": "risk_analysis", "status": "completed", "result": result}


async def _run_output_workflow(
    request, user_id, conversation_id, organisation_id, document_ids, db
):
    from app.agents.output_generation_agent import generate_output

    await manager.send_to_user(
        user_id=user_id,
        message={"event": "orchestrator_progress", "step": "generating_output"},
    )

    result = await generate_output(
        request=request,
        user_id=user_id,
        organisation_id=organisation_id,
        document_ids=document_ids,
        db=db,
    )

    return {"intent": "generate_output", "status": "completed", "result": result}


async def _run_extraction_workflow(
    request, user_id, conversation_id, organisation_id, document_ids, db
):
    from app.services.workflows import run_review_extraction

    await manager.send_to_user(
        user_id=user_id,
        message={"event": "orchestrator_progress", "step": "extracting_clauses"},
    )

    result = await run_review_extraction(
        request=request,
        user_id=user_id,
        organisation_id=organisation_id,
        document_ids=document_ids,
        db=db,
    )

    return {"intent": "extract_clauses", "status": "completed", "result": result}


async def _run_comparison_workflow(
    request, user_id, conversation_id, organisation_id, document_ids, db
):
    from app.services.workflows import run_version_comparison

    await manager.send_to_user(
        user_id=user_id,
        message={"event": "orchestrator_progress", "step": "comparing_versions"},
    )

    result = await run_version_comparison(
        request=request,
        user_id=user_id,
        organisation_id=organisation_id,
        document_ids=document_ids,
        db=db,
    )

    return {"intent": "compare_versions", "status": "completed", "result": result}


async def _run_aggregation_workflow(
    request, user_id, conversation_id, organisation_id, document_ids, db
):
    from app.services.workflows import run_data_aggregation

    await manager.send_to_user(
        user_id=user_id,
        message={"event": "orchestrator_progress", "step": "aggregating_data"},
    )

    result = await run_data_aggregation(
        request=request,
        user_id=user_id,
        organisation_id=organisation_id,
        document_ids=document_ids,
        db=db,
    )

    return {"intent": "aggregate_data", "status": "completed", "result": result}


async def _run_reference_workflow(
    request, user_id, conversation_id, organisation_id, document_ids, db
):
    from app.services.workflows import run_reference_list

    await manager.send_to_user(
        user_id=user_id,
        message={"event": "orchestrator_progress", "step": "generating_references"},
    )

    result = await run_reference_list(
        request=request,
        user_id=user_id,
        organisation_id=organisation_id,
        document_ids=document_ids,
        db=db,
    )

    return {"intent": "generate_references", "status": "completed", "result": result}
