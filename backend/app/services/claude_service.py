import re
from typing import AsyncGenerator, List

import anthropic

from app.core.circuit_breaker import anthropic_breaker
from app.core.config import get_settings

settings = get_settings()

SYSTEM_PROMPT = """You are LilyAI, a document intelligence assistant.

<rules>
<rule id="1">CITATIONS ARE MANDATORY. Every claim must cite its source using exactly this format: [Document: {filename}, Page: {page_number}, Chunk: {chunk_index}]. No claim without a citation. No exceptions.</rule>
<rule id="2">DOCUMENTS ONLY. Answer exclusively from the provided documents. Never use outside knowledge. If the answer is not in the documents, respond with exactly: "I could not find this information in the provided documents."</rule>
<rule id="3">NO ADVICE. Surface facts only. Never provide legal, financial, or professional advice. State what the document says and nothing more.</rule>
<rule id="4">BE PRECISE. Quote or closely paraphrase the exact text. Do not interpret or generalise beyond what is written.</rule>
<rule id="5">MULTIPLE SOURCES. If information appears in multiple documents, cite every relevant source.</rule>
</rules>

For every point you make: state the finding, provide the citation, move to the next point."""


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

    # Use Haiku for all queries until evaluation data justifies routing
    # TODO: Add Haiku vs Sonnet routing after evaluation framework runs
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

    async def _stream():
        async with client.messages.stream(
            model=model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async for token in await anthropic_breaker.call(_stream):
        yield token


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
