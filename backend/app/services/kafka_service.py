
import json
import logging

from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = ["localhost:9092"]


def create_kafka_producer():
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda value: json.dumps(
            value, default=str
        ).encode("utf-8"),
        key_serializer=lambda key: key.encode("utf-8") if key else None,
        acks="all",
        retries=5,
        max_in_flight_requests_per_connection=1
    )


def publish_event(topic: str, event: dict, key: str | None = None):
    producer = create_kafka_producer()

    try:
        future = producer.send(
            topic,
            key=key,
            value=event
        )

        result = future.get(timeout=10)

        logger.info(
            "Kafka event published: topic=%s partition=%s offset=%s",
            result.topic,
            result.partition,
            result.offset
        )

        return {
            "topic": result.topic,
            "partition": result.partition,
            "offset": result.offset
        }

    except KafkaError:
        logger.exception("Failed to publish Kafka event")
        raise

    finally:
        producer.close()

def publish_dead_letter_event(
    original_topic: str,
    event: dict,
    error_message: str,
    retry_count: int
):
    from datetime import datetime, timezone

    dlq_topic = f"{original_topic}-dlq"

    dead_letter_event = {
        "original_topic": original_topic,
        "original_event": event,
        "error_message": error_message,
        "retry_count": retry_count,
        "failed_at": datetime.now(timezone.utc).isoformat()
    }

    return publish_event(
        topic=dlq_topic,
        event=dead_letter_event,
        key=str(event.get("event_id", "unknown"))
    )
