
from sqlalchemy import (
    BigInteger,
    Column,
    Integer,
    String,
    Date,
    Numeric,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    text
)

from backend.app.database.base import Base


class MedicineBatch(Base):

    __tablename__ = "medicine_batches"

    batch_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    medicine_id = Column(
        BigInteger,
        ForeignKey("medicines.medicine_id"),
        nullable=False
    )

    supplier_id = Column(
        BigInteger,
        ForeignKey("suppliers.supplier_id")
    )

    batch_number = Column(String(100), nullable=False)
    manufactured_on = Column(Date)
    expires_on = Column(Date, nullable=False)
    received_quantity = Column(Integer, nullable=False)
    unit_cost = Column(Numeric(12, 2))

    batch_status = Column(
        String(30),
        server_default=text("'AVAILABLE'")
    )

    __table_args__ = (
        UniqueConstraint(
            "medicine_id",
            "supplier_id",
            "batch_number"
        ),
        CheckConstraint(
            "received_quantity > 0"
        ),
        CheckConstraint(
            "manufactured_on IS NULL OR expires_on > manufactured_on"
        ),
        CheckConstraint(
            "batch_status IN ('AVAILABLE', 'QUARANTINED', 'RECALLED')"
        ),
        Index("idx_batches_medicine", "medicine_id")
    )
