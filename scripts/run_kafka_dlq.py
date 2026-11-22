
from backend.app.services.kafka_service import publish_event

invalid_event = {
    "event_id": "DLQ-TEST-001",
    "event_type": "INVALID_EVENT",
    "facility_id": 1,
    "medicine_id": 1,
    "batch_id": 1,
    "quantity": 10
}

result = publish_event(
    topic="inventory-events",
    event=invalid_event,
    key="dlq-test-001"
)

print("Invalid test event published!")
print(result)
