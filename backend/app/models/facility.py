
from sqlalchemy import BigInteger, Column, String, TIMESTAMP, text
from backend.app.database.base import Base


class Facility(Base):

    __tablename__ = "facilities"

    facility_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    facility_name = Column(String(200), nullable=False)
    facility_type = Column(String(50), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)

    created_at = Column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP")
    )
