import json
import logging
import time

from kafka import TopicPartition
from kafka.structs import OffsetAndMetadata

from backend.app.services.kafka_service import (
    publish_dead_letter_event
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


def handle_kafka_message(
    consumer,
    message,
    processor,
    stream_name: str
) -> bool:

    try:
        raw_message = message.value.decode(
            "utf-8",
            errors="replace"
        )

        try:
            event = json.loads(raw_message)

        except json.JSONDecodeError as error:

            logger.error(
                "%s: Malformed JSON at partition %s offset %s",
                stream_name,
                message.partition,
                message.offset
            )

            publish_dead_letter_event(
                original_topic=message.topic,
                event={
                    "malformed_message": raw_message,
                    "partition": message.partition,
                    "offset": message.offset
                },
                error_message=f"Malformed JSON: {error}",
                retry_count=0
            )

        else:

            success = False
            last_error = None

            for attempt in range(1, MAX_RETRIES + 1):

                try:
                    processor(event, message.topic)
                    success = True
                    break

                except Exception as error:

                    last_error = error

                    logger.warning(
                        "%s processing failed. Attempt %s/%s: %s",
                        stream_name,
                        attempt,
                        MAX_RETRIES,
                        error
                    )

                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY_SECONDS)

            if not success:

                publish_dead_letter_event(
                    original_topic=message.topic,
                    event=event,
                    error_message=str(last_error),
                    retry_count=MAX_RETRIES
                )

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

        logger.info(
            "%s: Offset committed. Partition=%s Offset=%s",
            stream_name,
            message.partition,
            message.offset
        )

        return True

    except Exception:

        logger.exception(
            "%s: Message handling failed. Offset not committed.",
            stream_name
        )

        return False
