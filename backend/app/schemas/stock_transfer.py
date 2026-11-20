
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class StockTransferCreate(BaseModel):

    source_facility_id: int = Field(gt=0)

    destination_facility_id: int = Field(gt=0)

    batch_id: int = Field(gt=0)

    quantity: int = Field(gt=0)

    remarks: str | None = Field(
        default=None,
        max_length=500
    )


class StockTransferStatusUpdate(BaseModel):

    status: Literal[
        "APPROVED",
        "REJECTED",
        "CANCELLED"
    ]

    remarks: str | None = Field(
        default=None,
        max_length=500
    )


class StockTransferResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    transfer_id: int

    source_facility_id: int

    destination_facility_id: int

    batch_id: int

    quantity: int

    status: str

    requested_at: datetime

    approved_at: datetime | None

    dispatched_at: datetime | None

    received_at: datetime | None

    remarks: str | None
