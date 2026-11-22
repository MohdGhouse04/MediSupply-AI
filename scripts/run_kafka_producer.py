
from backend.app.services.kafka_service import publish_event

event = {
    "event_type": "INVENTORY_RECEIVED",
    "facility_id": 1,
    "medicine_id": 1,
    "batch_id": 8,
    "quantity": 100,
    "source": "MediSupply AI",
    "message": "Test inventory event"
}

result = publish_event(
    topic="inventory-events",
    event=event,
    key="facility-1-medicine-1"
)

print("Kafka event published successfully!")
print(result)
