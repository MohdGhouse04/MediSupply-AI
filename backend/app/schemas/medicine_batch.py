
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MedicineBatchCreate(BaseModel):

    medicine_id: int = Field(gt=0)
    supplier_id: int | None = Field(default=None, gt=0)

    batch_number: str = Field(min_length=1, max_length=100)

    manufactured_on: date | None = None
    expires_on: date

    received_quantity: int = Field(gt=0)
    unit_cost: Decimal | None = Field(default=None, ge=0)

    batch_status: Literal[
        "AVAILABLE",
        "QUARANTINED",
        "RECALLED"
    ] = "AVAILABLE"

    @model_validator(mode="after")
    def validate_dates(self):

        if (
            self.manufactured_on is not None
            and self.expires_on <= self.manufactured_on
        ):
            raise ValueError(
                "Expiry date must be after manufacturing date"
            )

        return self


class MedicineBatchUpdate(BaseModel):

    medicine_id: int = Field(gt=0)
    supplier_id: int | None = Field(default=None, gt=0)

    batch_number: str = Field(min_length=1, max_length=100)

    manufactured_on: date | None = None
    expires_on: date

    received_quantity: int = Field(gt=0)
    unit_cost: Decimal | None = Field(default=None, ge=0)

    batch_status: Literal[
        "AVAILABLE",
        "QUARANTINED",
        "RECALLED"
    ]

    @model_validator(mode="after")
    def validate_dates(self):

        if (
            self.manufactured_on is not None
            and self.expires_on <= self.manufactured_on
        ):
            raise ValueError(
                "Expiry date must be after manufacturing date"
            )

        return self


class MedicineBatchResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    batch_id: int
    medicine_id: int
    supplier_id: int | None

    batch_number: str
    manufactured_on: date | None
    expires_on: date

    received_quantity: int
    unit_cost: Decimal | None
    batch_status: str
