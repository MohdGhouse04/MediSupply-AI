
from pydantic import BaseModel, ConfigDict


class ProcurementRecommendationResponse(BaseModel):

    model_config = ConfigDict(extra="allow")

    facility_id: int
    facility_name: str

    medicine_id: int
    medicine_name: str
    strength: str
    unit: str

    usable_stock: int
    planning_available_stock: int

    approved_outgoing_transfer_quantity: int

    forecast_7_day: float
    forecast_14_day: float
    forecast_30_day: float

    average_daily_demand: float
    safety_stock: float
    required_stock: float

    days_of_stock: float | None

    gross_procurement_gap: float
    recommended_procurement_quantity: int

    pending_inbound_transfer_quantity: int
    approved_inbound_transfer_quantity: int
    dispatched_inbound_transfer_quantity: int
    potential_inbound_transfer_quantity: int

    provisional_procurement_quantity_after_transfers: int

    urgency: str
    action: str

    safety_stock_days: int
    approval_required: bool
    forecast_is_synthetic: bool


class ProcurementRecommendationList(BaseModel):

    total_recommendations: int
    safety_days: int

    recommendations: list[ProcurementRecommendationResponse]
