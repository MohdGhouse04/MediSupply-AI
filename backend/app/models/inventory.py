
from sqlalchemy import (
    BigInteger,
    Column,
    Integer,
    ForeignKey,
    TIMESTAMP,
    UniqueConstraint,
    CheckConstraint,
    Index,
    text
)

from backend.app.database.base import Base


class Inventory(Base):

    __tablename__ = "inventory"

    inventory_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    facility_id = Column(
        BigInteger,
        ForeignKey("facilities.facility_id"),
        nullable=False
    )

    batch_id = Column(
        BigInteger,
        ForeignKey("medicine_batches.batch_id"),
        nullable=False
    )

    quantity_on_hand = Column(
        Integer,
        nullable=False,
        server_default=text("0")
    )

    reserved_quantity = Column(
        Integer,
        nullable=False,
        server_default=text("0")
    )

    damaged_quantity = Column(
        Integer,
        nullable=False,
        server_default=text("0")
    )

    updated_at = Column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP")
    )

    __table_args__ = (
        UniqueConstraint("facility_id", "batch_id"),
        CheckConstraint("quantity_on_hand >= 0"),
        CheckConstraint("reserved_quantity >= 0"),
        CheckConstraint("damaged_quantity >= 0"),
        CheckConstraint(
            "reserved_quantity + damaged_quantity <= quantity_on_hand"
        ),
        Index("idx_inventory_batch", "batch_id"),
        Index("idx_inventory_facility", "facility_id")
    )
