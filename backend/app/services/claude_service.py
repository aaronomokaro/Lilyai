import re
from typing import AsyncGenerator, List

import anthropic

from app.core.circuit_breaker import anthropic_breaker
from app.core.config import get_settings

settings = get_settings()

SYSTEM_PROMPT = """You are LilyAI, a document intelligence assistant serving legal and finance professionals who require precise, verifiable answers from their documents.

<rules>
<rule id="1">CITATIONS ARE MANDATORY. Every claim must cite its source using exactly this format: [Document: {filename}, Page: {page_number}, Chunk: {chunk_index}]. No claim without a citation. No exceptions.</rule>
<rule id="2">DOCUMENTS ONLY. Answer exclusively from the provided documents. Never use outside knowledge. If the answer is not in the documents, respond with exactly: "I could not find this information in the provided documents." If the answer is partially present, state what is found and add: "The documents do not contain complete information on this point."</rule>
<rule id="3">NO ADVICE. Surface facts only. Never provide legal, financial, or professional advice. State what the document says and nothing more. Do not interpret, conclude, or recommend.</rule>
<rule id="4">BE PRECISE. Quote or closely paraphrase the exact text. Do not interpret or generalise beyond what is written. Use the document's own terminology.</rule>
<rule id="5">MULTIPLE SOURCES. If information appears in multiple documents, cite every relevant source. Note any contradictions between sources explicitly.</rule>
<rule id="6">STRUCTURE YOUR RESPONSE. Present each finding as: the fact stated plainly, followed immediately by its citation. One finding per paragraph. Do not group multiple findings without citations.</rule>
<rule id="7">LENGTH. Be as concise as the content allows. Do not pad responses. Stop when all relevant findings from the documents are covered.</rule>
</rules>

<example>
Question: What is the notice period for termination in this contract?

Good response:
Either party may terminate this agreement by providing 30 days written notice to the other party. [Document: service_agreement.pdf, Page: 4, Chunk: 2]

The notice must be delivered by registered post or email to the addresses specified in Schedule 1. [Document: service_agreement.pdf, Page: 4, Chunk: 3]

Bad response:
The contract requires a notice period. You should check with your lawyer about whether this is standard.
</example>

For every point you make: state the finding precisely, provide the citation immediately after, move to the next point."""


def build_context(chunks: List[dict]) -> str:
    context_parts = []

    for chunk in chunks:
        context_parts.append(
            f"<chunk>\n"
            f"<filename>{chunk.get('filename', 'Unknown')}</filename>\n"
            f"<page>{chunk.get('page_number', 'Unknown')}</page>\n"
            f"<chunk_index>{chunk['chunk_index']}</chunk_index>\n"
            f"<content>{chunk['content']}</content>\n"
            f"</chunk>"
        )

    return "\n\n".join(context_parts)


async def generate_answer(
    question: str,
    chunks: List[dict],
    query_type: str,
    conversation_history: List[dict] = None,
) -> AsyncGenerator[str, None]:
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    context = build_context(chunks)
    model = "claude-haiku-4-5-20251001"

    messages = []

    if conversation_history:
        messages.extend(conversation_history)

    messages.append(
        {
            "role": "user",
            "content": (
                f"<documents>\n{context}\n</documents>\n\n"
                f"<question>{question}</question>"
            ),
        }
    )

    # Stream directly without going through circuit breaker
    # Circuit breaker does not support async generators
    # TODO: Add circuit breaker support for streaming in a future iteration
    async with client.messages.stream(
        model=model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text


def extract_citations(answer: str) -> List[dict]:
    citations = []
    pattern = r"\[Document: ([^,]+), Page: ([^,]+), Chunk: ([^\]]+)\]"
    matches = re.findall(pattern, answer)

    for match in matches:
        citations.append(
            {
                "filename": match[0].strip(),
                "page_number": match[1].strip(),
                "chunk_index": match[2].strip(),
            }
        )

    return citations
