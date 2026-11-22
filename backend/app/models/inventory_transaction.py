
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Identity,
    text
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class InventoryTransaction(Base):

    __tablename__ = "inventory_transactions"

    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('RECEIVED', 'ISSUED', 'DAMAGED', 'ADJUSTMENT')",
            name="inventory_transactions_transaction_type_check"
        ),

        CheckConstraint(
            "quantity > 0",
            name="inventory_transactions_quantity_check"
        ),

        CheckConstraint(
            "adjustment_direction IS NULL OR "
            "adjustment_direction IN ('INCREASE', 'DECREASE')",
            name="valid_adjustment_direction"
        ),

        CheckConstraint(
            "(transaction_type = 'ADJUSTMENT' "
            "AND adjustment_direction IS NOT NULL) OR "
            "(transaction_type != 'ADJUSTMENT' "
            "AND adjustment_direction IS NULL)",
            name="adjustment_direction_required_check"
        ),
    )

    transaction_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True
    )

    facility_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("facilities.facility_id"),
        nullable=False
    )

    batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("medicine_batches.batch_id"),
        nullable=False
    )

    transaction_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    adjustment_direction: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True
    )

    transaction_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP")
    )

    reference_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    remarks: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
