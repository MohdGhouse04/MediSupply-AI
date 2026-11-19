
from sqlalchemy import BigInteger, Column, String, TIMESTAMP, text
from backend.app.database.base import Base


class Supplier(Base):

    __tablename__ = "suppliers"

    supplier_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    supplier_name = Column(String(200), nullable=False)
    contact_email = Column(String(200))
    contact_phone = Column(String(20))
    city = Column(String(100))
    state = Column(String(100))

    created_at = Column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP")
    )
