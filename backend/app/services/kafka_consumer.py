import logging

from kafka import KafkaConsumer

from sqlalchemy.dialects.postgresql import insert

from backend.app.database.connection import SessionLocal
from backend.app.models.processed_event import ProcessedEvent

from backend.app.services.kafka_message_handler import (
    handle_kafka_message
)

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = ["localhost:9092"]


def process_inventory_event(
    event: dict,
    topic: str = "inventory-events"
) -> bool:

    if not isinstance(event, dict):
        raise ValueError("Event must be a dictionary")

    event_id = event.get("event_id")
    event_type = event.get("event_type")

    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError("Missing or invalid event_id")

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

    if (
        not isinstance(event["quantity"], (int, float))
        or isinstance(event["quantity"], bool)
        or event["quantity"] <= 0
    ):
        raise ValueError("Invalid inventory event quantity")

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
                index_elements=["event_id"]
            )
            .returning(ProcessedEvent.event_id)
        )

        result = db.execute(statement).scalar_one_or_none()

        if result is None:

            db.rollback()

            logger.info(
                "Duplicate inventory event skipped: %s",
                event_id
            )

            print("Duplicate event skipped:", event_id)

            return False

        db.commit()

        print(
            f"Processed event: {event_type} | "
            f"Facility: {event['facility_id']} | "
            f"Medicine: {event['medicine_id']} | "
            f"Quantity: {event['quantity']}"
        )

        return True

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


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

            success = handle_kafka_message(
                consumer=consumer,
                message=message,
                processor=process_inventory_event,
                stream_name="Inventory"
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

    consume_inventory_events()
