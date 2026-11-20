
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    String,
    TIMESTAMP,
    text
)

from backend.app.database.base import Base


class Medicine(Base):

    __tablename__ = "medicines"

    medicine_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    generic_name = Column(
        String(200),
        nullable=False
    )

    brand_name = Column(String(200))

    strength = Column(
        String(100),
        nullable=False
    )

    dosage_form = Column(
        String(100),
        nullable=False
    )

    unit = Column(
        String(50),
        nullable=False
    )

    category = Column(String(100))

    nlem_listed = Column(
        Boolean,
        server_default=text("false")
    )

    created_at = Column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP")
    )
