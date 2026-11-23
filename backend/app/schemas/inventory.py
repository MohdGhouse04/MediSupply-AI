
from datetime import date
from pydantic import BaseModel


class InventoryResponse(BaseModel):

    facility_id: int
    batch_id: int
    medicine_id: int

    facility_name: str
    generic_name: str
    strength: str
    batch_number: str
    expires_on: date

    quantity_on_hand: int
    reserved_quantity: int
    damaged_quantity: int
    usable_stock: int
