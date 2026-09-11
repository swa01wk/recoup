"""
SQS Poller — Phase 6b Priority 7.

Polls ``recoup-recovery-events`` on a background thread when the backend starts
with live AWS resources configured.  When a Health event message arrives
(e.g. fired by ``scripts/fire_demo_event.py`` via EventBridge), the poller
automatically starts the canonical replay workflow — no manual API call needed.

The poller is non-blocking: it runs as a daemon thread and never prevents
graceful shutdown.  Failures are logged and retried on the next poll cycle.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_poller_thread: threading.Thread | None = None
_stop_event = threading.Event()

POLL_INTERVAL_SECONDS = 5
VISIBILITY_TIMEOUT = 30  # seconds — enough time to start the workflow


def _process_message(body: str, receipt_handle: str, sqs_client: Any, queue_url: str) -> None:
    """Handle a single SQS message body."""
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("SQS poller: could not parse message body as JSON")
        return

    detail_type = payload.get("detail-type") or payload.get("DetailType", "")
    source = payload.get("source", "")
    event_type = payload.get("event_type", "")

    # Health event routed by EventBridge → auto-trigger replay
    if source == "aws.health" or detail_type == "AWS Health Event":
        logger.info(
            "SQS poller: AWS Health event received — auto-triggering canonical replay"
        )
        try:
            from .api.routes.replay import _run_canonical  # noqa: PLC0415

            result = _run_canonical(opportunity_id=None)
            logger.info(
                "SQS poller: replay triggered — opportunity %s, credit %s",
                result.get("opportunity_id"),
                result.get("potential_credit"),
            )
            # Only ack AFTER successful processing
            sqs_client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
        except Exception:  # noqa: BLE001
            logger.warning(
                "SQS poller: replay trigger failed — message left in queue for retry",
                exc_info=True,
            )
            # Do NOT delete — let SQS redeliver up to maxReceiveCount then route to DLQ
        return

    # ACTION_EXECUTED or OPPORTUNITY_DETECTED — log and delete
    if event_type in ("OPPORTUNITY_DETECTED", "ACTION_EXECUTED"):
        logger.debug(
            "SQS poller: received %s event for %s",
            event_type,
            payload.get("opportunity_id"),
        )
        sqs_client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
        return

    # Unknown message — check receive count; route to DLQ after threshold
    receive_count = int(payload.get("ApproximateReceiveCount", 1))
    if receive_count >= 3:
        logger.warning(
            "SQS poller: unknown message exceeded max retries (%d), deleting to prevent DLQ backlog",
            receive_count,
        )
        sqs_client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
    else:
        logger.debug("SQS poller: unknown message type, leaving in queue: %s", body[:200])


def _poll_loop(queue_url: str, region: str) -> None:
    """Main polling loop — runs until _stop_event is set."""
    import boto3

    sqs = boto3.client("sqs", region_name=region)
    logger.info("SQS poller started: %s (poll interval: %ds)", queue_url, POLL_INTERVAL_SECONDS)

    while not _stop_event.is_set():
        try:
            resp = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=5,
                WaitTimeSeconds=POLL_INTERVAL_SECONDS,
                VisibilityTimeout=VISIBILITY_TIMEOUT,
                AttributeNames=["All"],
                MessageAttributeNames=["All"],
            )
            messages = resp.get("Messages", [])
            for msg in messages:
                body = msg.get("Body", "")
                receipt = msg.get("ReceiptHandle", "")
                _process_message(body, receipt, sqs, queue_url)
        except Exception:  # noqa: BLE001
            logger.warning(
                "SQS poller: receive error (retrying in %ds)",
                POLL_INTERVAL_SECONDS,
                exc_info=True,
            )
            time.sleep(POLL_INTERVAL_SECONDS)

    logger.info("SQS poller stopped.")


def start_poller() -> None:
    """
    Start the background SQS poller thread.

    No-op when:
    - No live AWS resources are configured
    - RECOUP_RECOVERY_EVENTS_QUEUE_URL is not set
    - The poller thread is already running
    """
    global _poller_thread  # noqa: PLW0603

    from .config import settings  # local import  # noqa: PLC0415

    if not settings.live_aws_enabled:
        logger.debug("SQS poller: disabled (no live AWS resources configured)")
        return

    if not settings.recovery_events_queue_url:
        logger.debug("SQS poller: disabled (RECOUP_RECOVERY_EVENTS_QUEUE_URL not set)")
        return

    if _poller_thread is not None and _poller_thread.is_alive():
        logger.debug("SQS poller: already running")
        return

    _stop_event.clear()
    _poller_thread = threading.Thread(
        target=_poll_loop,
        args=(settings.recovery_events_queue_url, settings.bedrock_region),
        daemon=True,
        name="sqs-poller",
    )
    _poller_thread.start()
    logger.info("SQS poller thread started (daemon=True)")


def stop_poller() -> None:
    """Signal the poller loop to exit gracefully."""
    _stop_event.set()
    if _poller_thread is not None:
        _poller_thread.join(timeout=10)
