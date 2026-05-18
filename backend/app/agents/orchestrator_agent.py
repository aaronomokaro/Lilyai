import asyncio
from typing import Any

import anthropic

from app.core.config import get_settings
from app.services.websocket_service import manager

settings = get_settings()

INTENT_CLASSIFICATION_PROMPT = """You are classifying a user request for a document intelligence platform.

<request>{request}</request>

Classify the intent into exactly one of these categories:
- query: user is asking a question about documents
- risk_analysis: user wants risks identified in documents
- extract_clauses: user wants specific clauses or fields extracted
- compare_versions: user wants two document versions compared
- aggregate_data: user wants data points pulled across multiple documents
- generate_output: user wants a report or structured output generated
- send_email: user wants to send something via Gmail
- save_to_drive: user wants to save something to Google Drive
- generate_references: user wants a reference list or bibliography

Respond with exactly one word from the list above. Nothing else."""


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
        max_tokens=20,
        messages=[
            {
                "role": "user",
                "content": INTENT_CLASSIFICATION_PROMPT.format(request=request),
            }
        ],
    )
    return response.content[0].text.strip().lower()


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

    else:
        # All other intents - treat as a query for now
        # Phase 6 adds dedicated workflows for extract, compare, aggregate, references
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
    from uuid import UUID

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
    from uuid import UUID

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
