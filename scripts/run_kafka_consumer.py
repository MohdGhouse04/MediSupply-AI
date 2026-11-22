
from backend.app.services.kafka_consumer import (
    consume_inventory_events
)

processed = consume_inventory_events(max_messages=1)

print(f"\nSuccessfully processed {processed} inventory events.")
