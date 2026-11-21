
from datetime import datetime, date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict, model_validator


class PurchaseOrderItemCreate(BaseModel):

    medicine_id: int = Field(gt=0)

    ordered_quantity: int = Field(gt=0)

    unit_cost: Decimal = Field(ge=0)


class PurchaseOrderCreate(BaseModel):

    facility_id: int = Field(gt=0)

    supplier_id: int = Field(gt=0)

    expected_delivery_date: datetime | None = None

    remarks: str | None = Field(default=None, max_length=500)

    items: list[PurchaseOrderItemCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_medicines(self):

        medicine_ids = [
            item.medicine_id for item in self.items
        ]

        if len(medicine_ids) != len(set(medicine_ids)):
            raise ValueError(
                "A medicine can appear only once in a purchase order"
            )

        return self


class PurchaseOrderStatusUpdate(BaseModel):

    status: Literal[
        "PENDING_APPROVAL",
        "APPROVED",
        "REJECTED",
        "ORDERED",
        "CANCELLED"
    ]

    remarks: str | None = Field(default=None, max_length=500)


class PurchaseOrderItemResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    purchase_order_item_id: int

    purchase_order_id: int

    medicine_id: int

    ordered_quantity: int

    received_quantity: int

    unit_cost: Decimal


class PurchaseOrderResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    purchase_order_id: int

    facility_id: int

    supplier_id: int

    status: str

    order_date: datetime

    expected_delivery_date: datetime | None

    approved_at: datetime | None

    ordered_at: datetime | None

    received_at: datetime | None

    total_amount: Decimal

    remarks: str | None

class PurchaseOrderReceiveItem(BaseModel):

    purchase_order_item_id: int = Field(gt=0)

    received_quantity: int = Field(gt=0)

    batch_number: str = Field(min_length=1, max_length=100)

    manufactured_on: date | None = None

    expires_on: date

    remarks: str | None = Field(default=None, max_length=500)

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


class PurchaseOrderReceive(BaseModel):

    items: list[PurchaseOrderReceiveItem] = Field(min_length=1)

    remarks: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_unique_items(self):

        item_ids = [
            item.purchase_order_item_id
            for item in self.items
        ]

        if len(item_ids) != len(set(item_ids)):
            raise ValueError(
                "A purchase order item can appear only once per receipt"
            )

        return self