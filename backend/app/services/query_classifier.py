import logging
import re
from enum import Enum
from typing import Tuple

import anthropic

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class QueryType(Enum):
    EXACT = "exact"
    CONCEPTUAL = "conceptual"
    MIXED = "mixed"
    CROSS_DOC = "cross_doc"
    RISK = "risk"


# top_k values per query type from the architecture
TOP_K_MAP = {
    QueryType.EXACT: 3,
    QueryType.CONCEPTUAL: 6,
    QueryType.MIXED: 5,
    QueryType.CROSS_DOC: 10,
    QueryType.RISK: 12,
}

# Keywords that strongly signal each query type
EXACT_SIGNALS = [
    "what is",
    "what are",
    "who is",
    "when is",
    "when was",
    "how much",
    "how many",
    "what date",
    "what number",
    "define",
    "definition of",
    "list the",
    "name the",
]

RISK_SIGNALS = [
    "risk",
    "risks",
    "liability",
    "liabilities",
    "exposure",
    "danger",
    "threat",
    "concern",
    "issue",
    "problem",
    "unusual",
    "missing",
    "anomaly",
    "red flag",
    "flag",
    "analyse risks",
    "analyze risks",
    "risk analysis",
]

CROSS_DOC_SIGNALS = [
    "compare",
    "comparison",
    "difference between",
    "differences between",
    "across documents",
    "across all",
    "between documents",
    "all documents",
    "each document",
    "summarise all",
    "summarize all",
]

QUERY_TYPE_CLASSIFICATION_PROMPT = """You are classifying the type of a question asked about documents, to determine the best retrieval strategy.

<question>{question}</question>

<types>
<type id="exact">A direct factual lookup with one specific answer. Example: "What is the contract value?"</type>
<type id="conceptual">A question requiring understanding or explanation of a concept spread across content. Example: "How does the liability structure work?"</type>
<type id="mixed">A question with both a factual and a conceptual element. Example: "What are the payment terms and how do they compare to standard practice?"</type>
<type id="cross_doc">A question requiring information pulled from or compared across multiple documents. Example: "Which of these contracts has the shortest notice period?"</type>
<type id="risk">A question asking to identify risks, issues, red flags, or concerns. Example: "What should I be worried about in this agreement?"</type>
</types>

Respond in this exact format:
<type>type_id</type>
<confidence>high|medium|low</confidence>"""


def _rule_based_classify(question_lower: str) -> QueryType:
    # Risk signals take highest priority
    for signal in RISK_SIGNALS:
        if signal in question_lower:
            return QueryType.RISK

    # Cross-document signals
    for signal in CROSS_DOC_SIGNALS:
        if signal in question_lower:
            return QueryType.CROSS_DOC

    # Exact signals
    for signal in EXACT_SIGNALS:
        if question_lower.startswith(signal) or f" {signal} " in question_lower:
            return QueryType.EXACT

    # No confident rule match
    return None


async def classify_query(question: str) -> Tuple[QueryType, int]:
    question_lower = question.lower().strip()

    rule_result = _rule_based_classify(question_lower)
    if rule_result is not None:
        return rule_result, TOP_K_MAP[rule_result]

    # Uncertain - escalate to Haiku instead of blindly defaulting to MIXED
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            messages=[
                {
                    "role": "user",
                    "content": QUERY_TYPE_CLASSIFICATION_PROMPT.format(
                        question=question
                    ),
                }
            ],
        )
        raw_text = response.content[0].text.strip()

        type_match = re.search(r"<type>(.*?)</type>", raw_text)
        confidence_match = re.search(r"<confidence>(.*?)</confidence>", raw_text)

        type_str = type_match.group(1).strip().lower() if type_match else "mixed"
        confidence = (
            confidence_match.group(1).strip().lower() if confidence_match else "low"
        )

        try:
            query_type = QueryType(type_str)
        except ValueError:
            query_type = QueryType.MIXED

        if confidence == "low":
            logger.warning(
                f"Low confidence query type classification: type={query_type.value}, "
                f"question={question[:100]}"
            )

        return query_type, TOP_K_MAP[query_type]

    except Exception as e:
        logger.error(f"Query type Haiku escalation failed, defaulting to MIXED: {e}")
        return QueryType.MIXED, TOP_K_MAP[QueryType.MIXED]
