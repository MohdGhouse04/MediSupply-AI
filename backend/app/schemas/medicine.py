
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field
)


class MedicineCreate(BaseModel):

    generic_name: str = Field(min_length=1, max_length=200)
    brand_name: str | None = Field(default=None, max_length=200)
    strength: str = Field(min_length=1, max_length=100)
    dosage_form: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=50)
    category: str | None = Field(default=None, max_length=100)
    nlem_listed: bool = False


class MedicineUpdate(BaseModel):

    generic_name: str = Field(min_length=1, max_length=200)
    brand_name: str | None = Field(default=None, max_length=200)
    strength: str = Field(min_length=1, max_length=100)
    dosage_form: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=50)
    category: str | None = Field(default=None, max_length=100)
    nlem_listed: bool = False


class MedicineResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    medicine_id: int
    generic_name: str
    brand_name: str | None
    strength: str
    dosage_form: str
    unit: str
    category: str | None
    nlem_listed: bool
    created_at: datetime
