from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class StockoutAlert(Base):

    __tablename__ = "stockout_alerts"

    __table_args__ = (
        UniqueConstraint(
            "facility_id",
            "medicine_id",
            "source_date",
            name="uq_stockout_alert_facility_medicine_date",
        ),
        Index("idx_stockout_alert_status", "risk_status"),
        Index("idx_stockout_alert_date", "source_date"),
    )

    alert_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )

    facility_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("facilities.facility_id"),
        nullable=False,
    )

    medicine_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("medicines.medicine_id"),
        nullable=False,
    )

    source_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    stockout_probability: Mapped[float] = mapped_column(
        Numeric(6, 4),
        nullable=False,
    )

    risk_threshold: Mapped[float] = mapped_column(
        Numeric(6, 4),
        nullable=False,
    )

    risk_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    alert_action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    previous_stock: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    previous_unmet_demand: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    demand_rolling_mean_7: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    demand_rolling_mean_14: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    demand_rolling_mean_30: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    acknowledged: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    acknowledged_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
