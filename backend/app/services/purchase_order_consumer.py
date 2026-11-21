
import json
import logging

from backend.app.core.config import settings
import time

from kafka import KafkaConsumer, TopicPartition
from kafka.structs import OffsetAndMetadata

from sqlalchemy.dialects.postgresql import insert

from backend.app.database.connection import SessionLocal
from backend.app.models.processed_event import ProcessedEvent

from backend.app.services.kafka_message_handler import (
    handle_kafka_message
)
from backend.app.services.kafka_service import (
    publish_dead_letter_event
)

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = [
    server.strip()
    for server in settings.KAFKA_BOOTSTRAP_SERVERS.split(",")
    if server.strip()
]

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


def process_purchase_order_event(
    event: dict,
    topic: str = "purchase-order-events"
) -> bool:

    if not isinstance(event, dict):
        raise ValueError("Event must be a dictionary")

    event_id = event.get("event_id")
    event_type = event.get("event_type")

    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError("Missing or invalid event_id")

    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(
            f"Invalid purchase order event type: {event_type}"
        )

    if not event.get("purchase_order_id"):
        raise ValueError("Missing purchase_order_id")

    db = SessionLocal()

    try:

        statement = (
            insert(ProcessedEvent)
            .values(
                event_id=event_id,
                topic=topic,
                event_type=event_type
            )
            .on_conflict_do_nothing(
                index_elements=[ProcessedEvent.event_id]
            )
            .returning(ProcessedEvent.event_id)
        )

        result = db.execute(statement).scalar_one_or_none()

        db.commit()

        if result is None:
            logger.info(
                "Duplicate purchase order event skipped: %s",
                event_id
            )
            print("Duplicate event skipped:", event_id)
            return False

        print("\n========== PURCHASE ORDER EVENT ==========")
        print("Event ID:", event_id)
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

        logger.info(
            "Purchase order event processed: %s",
            event_id
        )

        return True

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


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

            success = handle_kafka_message(
                consumer=consumer,
                message=message,
                processor=process_purchase_order_event,
                stream_name="Purchase Order"
            )

            if not success:
                break

            processed += 1

            if max_messages and processed >= max_messages:
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
