
from backend.app.services.kafka_service import publish_event

invalid_event = {
    "event_id": "PO-DLQ-TEST-001",
    "event_type": "INVALID_PURCHASE_ORDER_EVENT",
    "purchase_order_id": 3,
    "facility_id": 1,
    "supplier_id": 1
}

result = publish_event(
    topic="purchase-order-events",
    event=invalid_event,
    key="po-dlq-test-001"
)

print("Invalid purchase order event published!")
print(result)
