
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Identity,
    text
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class StockTransfer(Base):

    __tablename__ = "stock_transfers"

    __table_args__ = (

        CheckConstraint(
            "source_facility_id != destination_facility_id",
            name="different_transfer_facilities"
        ),

        CheckConstraint(
            "quantity > 0",
            name="positive_transfer_quantity"
        ),

        CheckConstraint(
            "status IN "
            "('PENDING', 'APPROVED', 'DISPATCHED', "
            "'RECEIVED', 'REJECTED', 'CANCELLED')",
            name="valid_transfer_status"
        ),
    )

    transfer_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True
    )

    source_facility_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("facilities.facility_id"),
        nullable=False
    )

    destination_facility_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("facilities.facility_id"),
        nullable=False
    )

    batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("medicine_batches.batch_id"),
        nullable=False
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'PENDING'")
    )

    requested_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    received_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    remarks: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )
