
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, EmailStr


class SupplierCreate(BaseModel):

    supplier_name: str = Field(min_length=1, max_length=200)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)


class SupplierUpdate(BaseModel):

    supplier_name: str = Field(min_length=1, max_length=200)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)


class SupplierResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    supplier_id: int
    supplier_name: str
    contact_email: str | None
    contact_phone: str | None
    city: str | None
    state: str | None
    created_at: datetime
