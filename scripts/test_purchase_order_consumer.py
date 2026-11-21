
from backend.app.services.purchase_order_consumer import (
    consume_purchase_order_events
)

processed = consume_purchase_order_events(max_messages=1)

print(f"\nSuccessfully processed {processed} purchase order events.")
