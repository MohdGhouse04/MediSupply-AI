
import json
import logging
import time

from kafka import KafkaConsumer, TopicPartition
from kafka.structs import OffsetAndMetadata

from backend.app.services.kafka_service import (
    publish_dead_letter_event
)

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = ["localhost:9092"]

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

VALID_EVENT_TYPES = {
    "PURCHASE_ORDER_CREATED",
    "PURCHASE_ORDER_PENDING_APPROVAL",
    "PURCHASE_ORDER_APPROVED",
    "PURCHASE_ORDER_REJECTED",
    "PURCHASE_ORDER_ORDERED",
    "PURCHASE_ORDER_CANCELLED",
    "PURCHASE_ORDER_PARTIALLY_RECEIVED",
    "PURCHASE_ORDER_RECEIVED",
}


def process_purchase_order_event(event: dict) -> bool:

    if not isinstance(event, dict):
        raise ValueError("Event must be a dictionary")

    event_type = event.get("event_type")

    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(
            f"Invalid purchase order event type: {event_type}"
        )

    if not event.get("purchase_order_id"):
        raise ValueError("Missing purchase_order_id")

    print("\n========== PURCHASE ORDER EVENT ==========")
    print("Event ID:", event.get("event_id"))
    print("Event Type:", event_type)
    print("Purchase Order ID:", event.get("purchase_order_id"))
    print("Facility ID:", event.get("facility_id"))
    print("Supplier ID:", event.get("supplier_id"))

    if event_type in {
        "PURCHASE_ORDER_PARTIALLY_RECEIVED",
        "PURCHASE_ORDER_RECEIVED"
    }:
        print("Received Items:", event.get("received_items", []))

    print("Event Timestamp:", event.get("event_timestamp"))

    return True


def consume_purchase_order_events(max_messages=None):

    consumer = KafkaConsumer(
        "purchase-order-events",
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="medisupply-purchase-order-consumer",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        max_poll_records=1,
        value_deserializer=None,
        key_deserializer=lambda key: (
            key.decode("utf-8") if key else None
        )
    )

    processed = 0

    try:
        print("Listening for purchase order events...")

        for message in consumer:

            try:
                event = json.loads(message.value.decode("utf-8"))

                success = False
                last_error = None

                for attempt in range(1, MAX_RETRIES + 1):

                    try:
                        process_purchase_order_event(event)
                        success = True
                        break

                    except Exception as error:
                        last_error = error

                        logger.warning(
                            "Purchase order processing failed. "
                            "Attempt %s/%s: %s",
                            attempt,
                            MAX_RETRIES,
                            error
                        )

                        if attempt < MAX_RETRIES:
                            time.sleep(RETRY_DELAY_SECONDS)

                if not success:

                    print("Maximum retries reached. Publishing to DLQ.")

                    publish_dead_letter_event(
                        original_topic=message.topic,
                        event=event,
                        error_message=str(last_error),
                        retry_count=MAX_RETRIES
                    )

                    print("Event successfully published to DLQ.")

                partition = TopicPartition(
                    message.topic,
                    message.partition
                )

                consumer.commit({
                    partition: OffsetAndMetadata(
                        message.offset + 1,
                        ""
                    )
                })

                processed += 1

                print(
                    "Partition:", message.partition,
                    "| Offset:", message.offset
                )

                if max_messages and processed >= max_messages:
                    break

            except Exception:
                logger.exception(
                    "Failed to process or publish purchase order event. "
                    "Offset not committed."
                )
                break

    except KeyboardInterrupt:
        print("Consumer stopped.")

    finally:
        consumer.close()

    return processed


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    consume_purchase_order_events()
