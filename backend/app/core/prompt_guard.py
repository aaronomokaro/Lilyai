import re

from fastapi import HTTPException, status

# Maximum question length - generous enough for complex professional queries
MAX_QUESTION_LENGTH = 2000

# Maximum number of tokens estimated from question length
# 1 token ≈ 4 characters - reject questions that would consume excessive context
MAX_QUESTION_TOKENS_ESTIMATE = 500

# Prompt injection patterns
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+instructions",
    r"forget\s+(everything|all|what)\s+(above|before|prior|previous)",
    r"you\s+are\s+now\s+a?\s+\w+\s+(ai|assistant|bot|model)",
    r"act\s+as\s+(if\s+)?(you\s+)?(have\s+no|without|ignore)",
    r"system\s*:\s*override",
    r"new\s+instructions?\s*:",
    r"your\s+(new\s+)?(instructions?|rules?|guidelines?)\s+are",
    r"disregard\s+(all\s+)?(previous|prior|above)",
    r"override\s+(all\s+)?(previous|prior|system)\s+(instructions?|rules?|prompts?)",
    r"pretend\s+(you\s+are|to\s+be)\s+(a\s+)?(different|new|unrestricted)",
    r"jailbreak",
    r"dan\s+mode",
    r"developer\s+mode",
]

COMPILED_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE) for pattern in INJECTION_PATTERNS
]


def check_prompt_injection(question: str) -> None:
    for pattern in COMPILED_INJECTION_PATTERNS:
        if pattern.search(question):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question contains invalid content.",
            )


def check_resource_exhaustion(question: str) -> None:
    if len(question) > MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Question too long. Maximum {MAX_QUESTION_LENGTH} characters.",
        )

    estimated_tokens = len(question) // 4
    if estimated_tokens > MAX_QUESTION_TOKENS_ESTIMATE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question is too complex. Please break it into smaller questions.",
        )


def validate_question(question: str) -> None:
    if not question or not question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty.",
        )

    check_resource_exhaustion(question)
    check_prompt_injection(question)
