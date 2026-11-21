
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    String,
    DateTime,
    Identity,
    text
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class ProcessedEvent(Base):

    __tablename__ = "processed_events"

    processed_event_id: Mapped[int] = mapped_column(
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

    processed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )
