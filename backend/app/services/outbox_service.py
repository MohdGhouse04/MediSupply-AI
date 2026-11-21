
from sqlalchemy.orm import Session

from backend.app.models.outbox_event import OutboxEvent


def add_outbox_event(
    db: Session,
    event: dict,
    topic: str
) -> OutboxEvent:
    """
    Add an event to the transactional outbox.

    The caller must commit the database transaction.
    This ensures the business operation and event record
    are committed or rolled back together.
    """

    event_id = str(event.get("event_id", "")).strip()
    event_type = event.get("event_type")

    if not event_id:
        raise ValueError("Event must contain a valid event_id")

    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("Event must contain a valid event_type")

    if not topic or not topic.strip():
        raise ValueError("Kafka topic is required")

    outbox_event = OutboxEvent(
        event_id=event_id,
        topic=topic,
        event_type=event_type,
        payload=event,
        status="PENDING",
        retry_count=0
    )

    db.add(outbox_event)

    return outbox_event
