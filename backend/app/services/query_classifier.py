from enum import Enum
from typing import Tuple


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


# TODO: Add confidence scoring. When confidence is low, escalate to Claude Haiku
# for classification. Current implementation defaults to MIXED for all uncertain queries.
def classify_query(question: str) -> Tuple[QueryType, int]:
    question_lower = question.lower().strip()

    # Risk signals take highest priority
    for signal in RISK_SIGNALS:
        if signal in question_lower:
            return QueryType.RISK, TOP_K_MAP[QueryType.RISK]

    # Cross-document signals
    for signal in CROSS_DOC_SIGNALS:
        if signal in question_lower:
            return QueryType.CROSS_DOC, TOP_K_MAP[QueryType.CROSS_DOC]

    # Exact signals
    for signal in EXACT_SIGNALS:
        if question_lower.startswith(signal) or f" {signal} " in question_lower:
            return QueryType.EXACT, TOP_K_MAP[QueryType.EXACT]

    # Default to mixed - handles most conversational queries
    return QueryType.MIXED, TOP_K_MAP[QueryType.MIXED]
