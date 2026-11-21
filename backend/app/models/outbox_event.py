
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    String,
    Text,
    DateTime,
    Integer,
    JSON,
    Identity,
    CheckConstraint,
    text
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class OutboxEvent(Base):

    __tablename__ = "outbox_events"

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'PUBLISHED', 'FAILED')",
            name="outbox_events_status_check"
        ),
        CheckConstraint(
            "retry_count >= 0",
            name="outbox_events_retry_count_check"
        ),
    )

    outbox_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True
    )

    event_id: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
        index=True
    )

    topic: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
        server_default=text("'PENDING'")
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
