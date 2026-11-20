
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db

from backend.app.services.procurement_recommendation_service import (
    get_procurement_recommendations
)

from backend.app.schemas.procurement import (
    ProcurementRecommendationList
)


router = APIRouter(
    prefix="/procurement",
    tags=["Procurement Recommendations"]
)


@router.get(
    "/recommendations",
    response_model=ProcurementRecommendationList
)
def read_procurement_recommendations(
    safety_days: int = Query(default=3, ge=0, le=30),
    db: Session = Depends(get_db)
):

    try:

        recommendations = get_procurement_recommendations(
            db,
            safety_days=safety_days
        )

        return {
            "total_recommendations": len(recommendations),
            "safety_days": safety_days,
            "recommendations": recommendations
        }

    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc)
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc)
        )

@router.get("/summary")
def read_procurement_summary(
    safety_days: int = Query(default=3, ge=0, le=30),
    db: Session = Depends(get_db)
):

    try:

        recommendations = get_procurement_recommendations(
            db,
            safety_days=safety_days
        )

        urgency_counts = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0
        }

        for item in recommendations:
            urgency_counts[item["urgency"]] += 1

        return {
            "total_recommendations": len(recommendations),

            "medicines_requiring_procurement": sum(
                1 for item in recommendations
                if item["action"] == "PROCUREMENT_RECOMMENDED"
            ),

            "urgency_breakdown": urgency_counts,

            "total_usable_stock": sum(
                item["usable_stock"]
                for item in recommendations
            ),

            "total_gross_procurement_quantity": sum(
                item["recommended_procurement_quantity"]
                for item in recommendations
            ),

            "total_provisional_procurement_quantity": sum(
                item["provisional_procurement_quantity_after_transfers"]
                for item in recommendations
            ),

            "total_pending_inbound": sum(
                item["pending_inbound_transfer_quantity"]
                for item in recommendations
            ),

            "total_approved_inbound": sum(
                item["approved_inbound_transfer_quantity"]
                for item in recommendations
            ),

            "total_dispatched_inbound": sum(
                item["dispatched_inbound_transfer_quantity"]
                for item in recommendations
            ),

            "safety_days": safety_days,

            "forecast_is_synthetic": True,

            "approval_required": True
        }

    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc)
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc)
        )
