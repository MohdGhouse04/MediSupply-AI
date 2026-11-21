
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.connection import SessionLocal
from backend.app.models.outbox_event import OutboxEvent
from backend.app.services.kafka_service import publish_event


logger = logging.getLogger(__name__)

MAX_RETRIES = 5


def publish_pending_events(batch_size: int = 10) -> dict:
    """
    Publish pending outbox events to Kafka.

    Uses FOR UPDATE SKIP LOCKED to prevent multiple
    publisher workers from claiming the same event.
    """

    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero")

    db: Session = SessionLocal()

    published_count = 0
    failed_count = 0
    processed_count = 0

    try:

        # 1. Claim pending events using row-level locks
        events = db.execute(
            select(OutboxEvent)
            .where(
                OutboxEvent.status == "PENDING",
                OutboxEvent.retry_count < MAX_RETRIES
            )
            .order_by(OutboxEvent.outbox_id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        ).scalars().all()

        if not events:
            return {
                "message": "No pending events found",
                "processed": 0,
                "published": 0,
                "failed": 0
            }

        for outbox_event in events:

            processed_count += 1

            try:

                # 2. Publish event to Kafka
                result = publish_event(
                    topic=outbox_event.topic,
                    event=outbox_event.payload,
                    key=str(outbox_event.payload.get("facility_id", outbox_event.event_id))
                )

                # 3. Mark event as published
                outbox_event.status = "PUBLISHED"
                outbox_event.published_at = datetime.now()
                outbox_event.last_error = None

                published_count += 1

                logger.info(
                    "Outbox event %s published: %s",
                    outbox_event.event_id,
                    result
                )

            except Exception as error:

                # 4. Record failed attempt
                outbox_event.retry_count += 1
                outbox_event.last_error = str(error)

                if outbox_event.retry_count >= MAX_RETRIES:
                    outbox_event.status = "FAILED"

                failed_count += 1

                logger.exception(
                    "Failed to publish outbox event %s",
                    outbox_event.event_id
                )

        # 5. Commit publication results
        db.commit()

        return {
            "message": "Outbox publishing completed",
            "processed": processed_count,
            "published": published_count,
            "failed": failed_count
        }

    except Exception:

        db.rollback()

        logger.exception(
            "Outbox publisher failed"
        )

        raise

    finally:
        db.close()


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )

    result = publish_pending_events(batch_size=10)

    print(result)
