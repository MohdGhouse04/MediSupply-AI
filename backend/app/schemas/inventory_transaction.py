
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    model_validator
)


class InventoryTransactionCreate(BaseModel):

    facility_id: int = Field(gt=0)
    batch_id: int = Field(gt=0)

    transaction_type: Literal[
        "RECEIVED",
        "ISSUED",
        "DAMAGED",
        "ADJUSTMENT"
    ]

    quantity: int = Field(gt=0)

    adjustment_direction: (
        Literal["INCREASE", "DECREASE"] | None
    ) = None

    reference_number: str | None = None
    remarks: str | None = None

    @model_validator(mode="after")
    def validate_adjustment_direction(self):

        if self.transaction_type == "ADJUSTMENT":
            if self.adjustment_direction is None:
                raise ValueError(
                    "adjustment_direction is required for ADJUSTMENT"
                )

        elif self.adjustment_direction is not None:
            raise ValueError(
                "adjustment_direction is only allowed for ADJUSTMENT"
            )

        return self


class InventoryTransactionResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    transaction_id: int
    facility_id: int
    batch_id: int
    transaction_type: str
    quantity: int
    adjustment_direction: str | None
    transaction_date: datetime
    reference_number: str | None
    remarks: str | None
