import logging
import signal
import time

from backend.app.services.outbox_publisher import publish_pending_events


logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2
BATCH_SIZE = 10

running = True


def stop_worker(signum, frame):
    global running

    logger.info("Shutdown signal received. Stopping outbox worker...")
    running = False


def run_outbox_worker():

    global running

    signal.signal(signal.SIGINT, stop_worker)
    signal.signal(signal.SIGTERM, stop_worker)

    logger.info("MediSupply Outbox Worker started")

    while running:

        try:

            result = publish_pending_events(
                batch_size=BATCH_SIZE
            )

            if result["processed"] > 0:

                logger.info(
                    "Outbox cycle completed | "
                    "Processed: %s | Published: %s | Failed: %s",
                    result["processed"],
                    result["published"],
                    result["failed"]
                )

        except Exception:

            logger.exception(
                "Outbox worker encountered an error"
            )

        if running:
            time.sleep(POLL_INTERVAL_SECONDS)

    logger.info("MediSupply Outbox Worker stopped")


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    run_outbox_worker()
