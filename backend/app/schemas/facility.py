
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FacilityCreate(BaseModel):

    facility_name: str = Field(min_length=1, max_length=200)

    facility_type: Literal[
        "HOSPITAL",
        "PHARMACY",
        "WAREHOUSE"
    ]

    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)


class FacilityUpdate(BaseModel):

    facility_name: str = Field(min_length=1, max_length=200)

    facility_type: Literal[
        "HOSPITAL",
        "PHARMACY",
        "WAREHOUSE"
    ]

    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)


class FacilityResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    facility_id: int
    facility_name: str
    facility_type: str
    city: str
    state: str
    created_at: datetime
