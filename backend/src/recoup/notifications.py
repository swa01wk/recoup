"""
Shared notification helpers — SNS and SQS.

All helpers fail silently: a notification failure must never block the main
demo flow. Each helper is guarded by ``settings.live_aws_enabled`` so
no real AWS calls are made in simulation mode.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# SNS
# ---------------------------------------------------------------------------


def format_recovery_report_email(
    opportunity_id: str,
    service: str,
    region: str,
    resource_id: str,
    savings_per_month: str,
    recommendation: str,
    severity: str,
    action: str,
) -> tuple[str, str]:
    """
    Format a structured recovery report email for SNS delivery.

    Returns (subject, message) ready for notify_sns().
    """
    console_links: dict[str, str] = {
        "EC2": f"https://console.aws.amazon.com/ec2/v2/home?region={region}#Instances",
        "RDS": f"https://console.aws.amazon.com/rds/home?region={region}#databases",
        "S3": f"https://s3.console.aws.amazon.com/s3/buckets?region={region}",
        "Lambda": f"https://console.aws.amazon.com/lambda/home?region={region}#/functions",
        "EBS": f"https://console.aws.amazon.com/ec2/v2/home?region={region}#Volumes",
        "EIP": f"https://console.aws.amazon.com/ec2/v2/home?region={region}#Addresses",
        "CloudWatch Logs": f"https://console.aws.amazon.com/cloudwatch/home?region={region}#logsV2",
    }
    console_url = console_links.get(service, f"https://console.aws.amazon.com/?region={region}")

    subject = f"[Recoup] Recovery Report — {service} · ${savings_per_month}/mo · {severity.upper()}"
    message = (
        f"Recoup Cost Recovery Report\n"
        f"{'=' * 50}\n\n"
        f"Opportunity ID : {opportunity_id}\n"
        f"Service        : {service}\n"
        f"Region         : {region}\n"
        f"Resource ID    : {resource_id}\n"
        f"Severity       : {severity.upper()}\n"
        f"Savings        : ${savings_per_month}/mo\n"
        f"Action         : {recommendation}\n"
        f"Recovery Type  : {action.replace('_', ' ').title()}\n\n"
        f"AWS Console    : {console_url}\n\n"
        f"This report was approved via the Recoup HITL Decision Inbox.\n"
        f"No destructive changes were made — this is an advisory report.\n\n"
        f"Timestamp: {_utcnow_iso()}\n"
        f"Recoup Hackathon Demo — AWS Spend Recovery Agent\n"
    )
    return subject, message


def notify_sns(subject: str, message: str) -> bool:
    """
    Publish a notification to the ``recoup-alerts`` SNS topic.

    Returns True if the message was published, False on any error or when
    live AWS is disabled.

    Guards:
    - ``settings.live_aws_enabled`` must be True
    - ``settings.recoup_sns_topic_arn`` must be non-empty
    """
    from .config import settings  # local import to avoid circular deps

    if not settings.live_aws_enabled:
        logger.debug("SNS notify skipped — live AWS disabled")
        return False

    topic_arn = settings.recoup_sns_topic_arn
    if not topic_arn:
        if settings.recoup_sns_dry_run:
            logger.info("SNS dry-run (no topic ARN): %s", subject)
            return True
        logger.warning("SNS notify skipped — RECOUP_SNS_TOPIC_ARN not set")
        return False

    if settings.recoup_sns_dry_run:
        logger.info("SNS dry-run publish to %s: %s", topic_arn, subject)
        return True

    try:
        import boto3

        sns = boto3.client("sns", region_name=settings.bedrock_region)
        sns.publish(TopicArn=topic_arn, Subject=subject[:100], Message=message)
        logger.info("SNS notification published: %s", subject)
        return True
    except Exception:  # noqa: BLE001
        logger.warning("SNS notify failed (non-fatal)", exc_info=True)
        return False


# ---------------------------------------------------------------------------
# SQS
# ---------------------------------------------------------------------------


def publish_opportunity_event(
    opportunity_id: str,
    opportunity_type: str,
    potential_value_usd: str,
    service: str,
    region: str = "us-east-1",
    requires_approval: bool = True,
    extra: dict[str, Any] | None = None,
) -> bool:
    """
    Publish a structured ``OPPORTUNITY_DETECTED`` event to the
    ``recoup-recovery-events`` SQS queue.

    Returns True if published, False on any error or when live AWS is disabled.

    Guards:
    - ``settings.live_aws_enabled`` must be True
    - ``settings.recovery_events_queue_url`` must be non-empty
    """
    from .config import settings  # local import to avoid circular deps

    if not settings.live_aws_enabled:
        logger.debug("SQS publish skipped — live AWS disabled")
        return False

    queue_url = settings.recovery_events_queue_url
    if not queue_url:
        logger.warning("SQS publish skipped — RECOUP_RECOVERY_EVENTS_QUEUE_URL not set")
        return False

    payload: dict[str, Any] = {
        "event_type": "OPPORTUNITY_DETECTED",
        "opportunity_id": opportunity_id,
        "type": opportunity_type,
        "potential_value_usd": potential_value_usd,
        "service": service,
        "region": region,
        "detected_at": _utcnow_iso(),
        "requires_approval": requires_approval,
    }
    if extra:
        payload.update(extra)

    try:
        import boto3

        sqs = boto3.client("sqs", region_name=settings.bedrock_region)
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(payload),
            MessageAttributes={
                "event_type": {
                    "DataType": "String",
                    "StringValue": "OPPORTUNITY_DETECTED",
                },
                "service": {
                    "DataType": "String",
                    "StringValue": service,
                },
            },
        )
        logger.info(
            "SQS opportunity event published: %s (%s)",
            opportunity_id,
            opportunity_type,
        )
        return True
    except Exception:  # noqa: BLE001
        logger.warning("SQS publish failed (non-fatal)", exc_info=True)
        return False


def publish_action_event(
    opportunity_id: str,
    action: str,
    result: str,
    service: str,
    region: str = "us-east-1",
    extra: dict[str, Any] | None = None,
) -> bool:
    """
    Publish a structured ``ACTION_EXECUTED`` event to the SQS queue.

    Used for completed actions such as EC2 instance stop.
    """
    from .config import settings  # local import to avoid circular deps

    if not settings.live_aws_enabled:
        logger.debug("SQS action event skipped — live AWS disabled")
        return False

    queue_url = settings.recovery_events_queue_url
    if not queue_url:
        return False

    payload: dict[str, Any] = {
        "event_type": "ACTION_EXECUTED",
        "opportunity_id": opportunity_id,
        "action": action,
        "result": result,
        "service": service,
        "region": region,
        "executed_at": _utcnow_iso(),
    }
    if extra:
        payload.update(extra)

    try:
        import boto3

        sqs = boto3.client("sqs", region_name=settings.bedrock_region)
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(payload),
            MessageAttributes={
                "event_type": {
                    "DataType": "String",
                    "StringValue": "ACTION_EXECUTED",
                },
            },
        )
        logger.info("SQS action event published: %s / %s", opportunity_id, action)
        return True
    except Exception:  # noqa: BLE001
        logger.warning("SQS action event failed (non-fatal)", exc_info=True)
        return False
