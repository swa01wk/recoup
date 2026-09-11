"""
OutcomeRepository — Sprint 3.

Persists CaseOutcome records to DynamoDB (recoup-outcome-metadata) and
powers the Recovery Ledger credit display.

When DynamoDB is not configured, records are kept in an in-memory dict so
the system still works in local / test mode.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog

from ..config import settings

log: structlog.BoundLogger = structlog.get_logger(__name__)

# In-memory fallback store (local / test mode)
_in_memory: dict[str, dict[str, Any]] = {}


class OutcomeRepository:
    """
    Read and write outcome records for the Recovery Ledger.

    Each record contains:
    - pk (partition key): "outcome#{opportunity_id}"
    - opportunity_id
    - credit_amount (Decimal)
    - action_taken (str)
    - outcome_state: "PENDING" | "RECOVERED" | "FAILED"
    - created_at (ISO timestamp)
    - recovered_at (ISO timestamp, when state=RECOVERED)
    """

    def _table(self) -> Any | None:
        if not settings.outcome_metadata_table:
            return None
        try:
            import boto3  # noqa: PLC0415

            ddb = boto3.resource("dynamodb", region_name=settings.bedrock_region)
            return ddb.Table(settings.outcome_metadata_table)
        except Exception as exc:  # noqa: BLE001
            log.warning("outcome_repository.dynamo_unavailable", error=str(exc))
            return None

    def create(
        self,
        opportunity_id: str,
        credit_amount: Decimal,
        action_taken: str,
    ) -> dict[str, Any]:
        """Create a new outcome record in PENDING state."""
        pk = f"outcome#{opportunity_id}"
        record: dict[str, Any] = {
            "pk": pk,
            "opportunity_id": opportunity_id,
            "credit_amount": str(credit_amount),
            "action_taken": action_taken,
            "outcome_state": "PENDING",
            "created_at": datetime.now(UTC).isoformat(),
            "recovered_at": None,
            "sns_sent": False,
            "sns_sent_at": None,
        }

        table = self._table()
        if table is not None:
            try:
                table.put_item(Item=record)
                log.info("outcome.created", opportunity_id=opportunity_id, credit=str(credit_amount))
            except Exception as exc:  # noqa: BLE001
                log.warning("outcome.dynamo_write_failed", error=str(exc))
        else:
            _in_memory[pk] = record
            log.debug("outcome.created.inmemory", opportunity_id=opportunity_id)

        return record

    def mark_recovered(self, opportunity_id: str, credit_amount: Decimal | None = None) -> dict[str, Any]:
        """Transition outcome to RECOVERED and record the final credit amount."""
        pk = f"outcome#{opportunity_id}"
        now = datetime.now(UTC).isoformat()

        table = self._table()
        if table is not None:
            try:
                update_expr = "SET outcome_state = :s, recovered_at = :t"
                expr_vals: dict[str, Any] = {":s": "RECOVERED", ":t": now}
                if credit_amount is not None:
                    update_expr += ", credit_amount = :c"
                    expr_vals[":c"] = str(credit_amount)
                table.update_item(
                    Key={"pk": pk},
                    UpdateExpression=update_expr,
                    ExpressionAttributeValues=expr_vals,
                )
                log.info("outcome.recovered", opportunity_id=opportunity_id)
            except Exception as exc:  # noqa: BLE001
                log.warning("outcome.dynamo_update_failed", error=str(exc))
        else:
            rec = _in_memory.get(pk, {"pk": pk, "opportunity_id": opportunity_id})
            rec.update({"outcome_state": "RECOVERED", "recovered_at": now})
            if credit_amount is not None:
                rec["credit_amount"] = str(credit_amount)
            _in_memory[pk] = rec

        return _in_memory.get(pk, {"pk": pk, "outcome_state": "RECOVERED"})

    def record_sns_notification(self, opportunity_id: str, sent: bool) -> None:
        """
        Record whether the SNS notification was successfully sent.

        Called by HITLFlow immediately after notify_sns() returns so the
        outcome record carries an honest sent/skipped status.
        """
        pk = f"outcome#{opportunity_id}"
        now = datetime.now(UTC).isoformat() if sent else None

        table = self._table()
        if table is not None:
            try:
                table.update_item(
                    Key={"pk": pk},
                    UpdateExpression="SET sns_sent = :s, sns_sent_at = :t",
                    ExpressionAttributeValues={":s": sent, ":t": now},
                )
                log.info("outcome.sns_recorded", opportunity_id=opportunity_id, sent=sent)
            except Exception as exc:  # noqa: BLE001
                log.warning("outcome.sns_record_failed", error=str(exc))
        else:
            rec = _in_memory.get(pk)
            if rec is None:
                # outcome may not exist yet if called before create(); create a stub
                rec = {"pk": pk, "opportunity_id": opportunity_id}
                _in_memory[pk] = rec
            rec["sns_sent"] = sent
            rec["sns_sent_at"] = now

    def get(self, opportunity_id: str) -> dict[str, Any] | None:
        """Retrieve outcome record for *opportunity_id*, or None if not found."""
        pk = f"outcome#{opportunity_id}"
        table = self._table()
        if table is not None:
            try:
                resp = table.get_item(Key={"pk": pk})
                return resp.get("Item")
            except Exception as exc:  # noqa: BLE001
                log.warning("outcome.dynamo_read_failed", error=str(exc))
        return _in_memory.get(pk)

    @staticmethod
    def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
        """Ensure opportunity_id is present (derive from pk when missing)."""
        if record.get("opportunity_id"):
            return record
        pk = record.get("pk", "")
        if isinstance(pk, str) and pk.startswith("outcome#"):
            record = {**record, "opportunity_id": pk[len("outcome#") :]}
        return record

    def list_all(self) -> list[dict[str, Any]]:
        """Return all outcome records (in-memory or DynamoDB scan)."""
        table = self._table()
        if table is not None:
            try:
                resp = table.scan()
                return [self._normalize_record(item) for item in resp.get("Items", [])]
            except Exception as exc:  # noqa: BLE001
                log.warning("outcome.dynamo_scan_failed", error=str(exc))
        return [self._normalize_record(item) for item in _in_memory.values()]

    def total_recovered_usd(self) -> Decimal:
        """Sum all credit_amount values where outcome_state=RECOVERED."""
        total = Decimal("0")
        for record in self.list_all():
            if record.get("outcome_state") == "RECOVERED":
                try:
                    total += Decimal(str(record.get("credit_amount", "0")))
                except Exception:  # noqa: BLE001
                    pass
        return total


    def clear_all(self) -> int:
        """
        Delete every outcome record — in-memory and DynamoDB.

        Used by the admin demo reset so stale "Recovered" rows from prior
        sessions don't bleed through into fresh demo runs.

        Returns the number of records deleted.
        """
        deleted = 0

        # Clear in-memory store
        deleted += len(_in_memory)
        _in_memory.clear()

        # Clear DynamoDB table (scan → batch delete)
        table = self._table()
        if table is not None:
            try:
                # Scan all PKs (we only need the key to delete)
                resp = table.scan(ProjectionExpression="pk")
                items = resp.get("Items", [])
                # Handle paginated scan
                while "LastEvaluatedKey" in resp:
                    resp = table.scan(
                        ProjectionExpression="pk",
                        ExclusiveStartKey=resp["LastEvaluatedKey"],
                    )
                    items.extend(resp.get("Items", []))

                # Batch-delete in chunks of 25 (DynamoDB limit)
                with table.batch_writer() as batch:
                    for item in items:
                        batch.delete_item(Key={"pk": item["pk"]})
                deleted += len(items)
                log.info("outcome.clear_all", deleted=deleted)
            except Exception as exc:  # noqa: BLE001
                log.warning("outcome.clear_all_failed", error=str(exc))

        return deleted


# Singleton instance
outcome_repo = OutcomeRepository()
