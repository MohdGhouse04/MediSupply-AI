
from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    String,
    DateTime,
    Numeric,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    text
)

from backend.app.database.base import Base


class PurchaseOrder(Base):

    __tablename__ = "purchase_orders"

    purchase_order_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    facility_id = Column(
        BigInteger,
        ForeignKey("facilities.facility_id"),
        nullable=False
    )

    supplier_id = Column(
        BigInteger,
        ForeignKey("suppliers.supplier_id"),
        nullable=False
    )

    status = Column(
        String(30),
        nullable=False,
        default="DRAFT",
        server_default="DRAFT"
    )

    order_date = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )

    expected_delivery_date = Column(
        DateTime,
        nullable=True
    )

    approved_at = Column(
        DateTime,
        nullable=True
    )

    ordered_at = Column(
        DateTime,
        nullable=True
    )

    received_at = Column(
        DateTime,
        nullable=True
    )

    total_amount = Column(
        Numeric(14, 2),
        nullable=False,
        default=0
    )

    remarks = Column(
        String(500),
        nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'PENDING_APPROVAL', "
            "'APPROVED', 'REJECTED', 'ORDERED', "
            "'PARTIALLY_RECEIVED', 'RECEIVED', 'CANCELLED')",
            name="valid_purchase_order_status"
        ),
        CheckConstraint(
            "total_amount >= 0",
            name="valid_purchase_order_amount"
        )
    )


class PurchaseOrderItem(Base):

    __tablename__ = "purchase_order_items"

    purchase_order_item_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    purchase_order_id = Column(
        BigInteger,
        ForeignKey("purchase_orders.purchase_order_id"),
        nullable=False
    )

    medicine_id = Column(
        BigInteger,
        ForeignKey("medicines.medicine_id"),
        nullable=False
    )

    ordered_quantity = Column(
        Integer,
        nullable=False
    )

    received_quantity = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0"
    )

    unit_cost = Column(
        Numeric(12, 2),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "purchase_order_id",
            "medicine_id",
            name="unique_purchase_order_medicine"
        ),
        CheckConstraint(
            "ordered_quantity > 0",
            name="valid_ordered_quantity"
        ),
        CheckConstraint(
            "received_quantity >= 0",
            name="valid_received_quantity"
        ),
        CheckConstraint(
            "received_quantity <= ordered_quantity",
            name="received_not_more_than_ordered"
        ),
        CheckConstraint(
            "unit_cost >= 0",
            name="valid_purchase_order_unit_cost"
        )
    )
