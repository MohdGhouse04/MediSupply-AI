
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


def process_inventory_event(event: dict) -> bool:

    if not isinstance(event, dict):
        raise ValueError("Event must be a dictionary")

    event_type = event.get("event_type")

    if not isinstance(event_type, str) or not event_type.startswith("INVENTORY_"):
        raise ValueError("Invalid inventory event type")

    required_fields = [
        "facility_id",
        "medicine_id",
        "batch_id",
        "quantity"
    ]

    for field in required_fields:
        if event.get(field) is None:
            raise ValueError(f"Missing required field: {field}")

    if not isinstance(event["quantity"], (int, float)) or event["quantity"] <= 0:
        raise ValueError("Invalid inventory event quantity")

    print(
        f"Processed event: {event_type} | "
        f"Facility: {event['facility_id']} | "
        f"Medicine: {event['medicine_id']} | "
        f"Quantity: {event['quantity']}"
    )

    return True


def consume_inventory_events(max_messages=None):

    consumer = KafkaConsumer(
        "inventory-events",
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="medisupply-inventory-consumer",
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
        print("Listening for inventory events...")

        for message in consumer:

            try:
                event = json.loads(message.value.decode("utf-8"))

                success = False
                last_error = None

                for attempt in range(1, MAX_RETRIES + 1):

                    try:
                        process_inventory_event(event)
                        success = True
                        break

                    except Exception as error:
                        last_error = error

                        logger.warning(
                            "Inventory event processing failed. "
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
                    "Failed to process or publish inventory event. "
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

    consume_inventory_events()
