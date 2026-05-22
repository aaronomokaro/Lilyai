from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.organisation import User
from app.services.evaluation_runner import run_evaluation

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


class EvaluationRequest(BaseModel):
    sample_size: Optional[int] = None


@router.post("/run")
async def run_evaluation_endpoint(
    request: EvaluationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation runs are restricted to admin users.",
        )

    result = await run_evaluation(
        user_id=str(current_user.id),
        organisation_id=(
            str(current_user.organisation_id) if current_user.organisation_id else None
        ),
        db=db,
        sample_size=request.sample_size,
    )

    return result


@router.get("/dataset/stats")
async def get_dataset_stats(
    current_user: User = Depends(get_current_user),
):
    from app.services.ground_truth import dataset

    return {
        "total_cases": dataset.count(),
        "by_capability": {
            capability: len(dataset.get_by_capability(capability))
            for capability in [
                "natural_language_questioning",
                "cross_document_analysis",
                "review_extraction",
                "data_aggregation",
                "risk_surfacing",
                "version_comparison",
                "reference_list",
            ]
        },
        "no_answer_cases": len(dataset.get_no_answer_cases()),
        "by_query_type": {
            query_type: len(dataset.get_by_query_type(query_type))
            for query_type in ["exact", "conceptual", "mixed", "cross_doc", "risk"]
        },
    }
