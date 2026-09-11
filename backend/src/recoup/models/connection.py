"""
CustomerConnection — abstraction for an AWS account integration point.

Same-account (hackathon):
    role_arn points to RecoupReadOnlyRole in the Recoup demo account.
Cross-account (production):
    role_arn points to RecoupReadOnlyRole in the customer account.
    Only the role ARN + account ID changes — code path is identical.

Usage::

    conn = CustomerConnection(
        role_arn="arn:aws:iam::625962218034:role/RecoupReadOnlyRole",
        external_id="recoup-demo-external-id",
    )
    session = conn.build_session()   # STS AssumeRole happens here
    ec2 = session.client("ec2")
"""

from __future__ import annotations

import hashlib
import time
from typing import TYPE_CHECKING, Any

import structlog
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    import boto3 as _boto3

log: structlog.BoundLogger = structlog.get_logger(__name__)

# Cache assumed credentials to avoid calling STS more than once per minute
# Key: sha256(role_arn + external_id), Value: (expiry_ts_utc, Session)
_SESSION_CACHE: dict[str, tuple[float, Any]] = {}


def _cache_key(role_arn: str, external_id: str) -> str:
    return hashlib.sha256(f"{role_arn}:{external_id}".encode()).hexdigest()


class CustomerConnection(BaseModel):
    """
    Represents a Recoup connection to one AWS account.

    - Same-account demo: ``role_arn`` points to ``RecoupReadOnlyRole`` in the
      hackathon account (account 625962218034).
    - Production cross-account: ``role_arn`` points to ``RecoupReadOnlyRole``
      in the *customer's* account.  Only this field changes — no code rewrite.
    """

    role_arn: str = Field(..., description="ARN of the analysis role to assume via STS")
    external_id: str = Field(
        ..., description="External ID matching the trust policy condition"
    )
    region: str = Field(default="us-east-1", description="AWS region for API calls")
    session_name: str = Field(
        default="recoup-analysis-session",
        description="IAM session name written to CloudTrail",
    )
    account_id: str | None = Field(
        default=None, description="Populated after successful STS assume"
    )
    assumed_role_arn: str | None = Field(
        default=None, description="Full ARN of the assumed-role session"
    )

    model_config = {"arbitrary_types_allowed": True}

    def build_session(self, *, use_cache: bool = True) -> Any:
        """
        Call ``sts:AssumeRole`` and return a scoped :class:`boto3.Session`.

        Credentials are cached for up to 50 minutes (well within the 1-hour
        expiry) to avoid redundant STS calls within a single scan workflow.
        Pass ``use_cache=False`` to force a fresh assume (useful in tests).

        Raises:
            botocore.exceptions.ClientError: When AssumeRole fails (wrong ARN,
                missing trust policy, incorrect External ID, etc.).
        """
        import boto3  # noqa: PLC0415

        ck = _cache_key(self.role_arn, self.external_id)
        if use_cache and ck in _SESSION_CACHE:
            expiry, cached_session = _SESSION_CACHE[ck]
            if time.time() < expiry:
                log.debug(
                    "sts.assume_role.cache_hit",
                    role_arn=self.role_arn,
                    ttl_remaining_s=round(expiry - time.time()),
                )
                return cached_session

        log.info(
            "sts.assume_role.start",
            role_arn=self.role_arn,
            session_name=self.session_name,
            region=self.region,
        )

        sts = boto3.client("sts")
        response = sts.assume_role(
            RoleArn=self.role_arn,
            RoleSessionName=self.session_name,
            ExternalId=self.external_id,
            DurationSeconds=3600,
        )

        creds = response["Credentials"]
        assumed_arn: str = response["AssumedRoleUser"]["Arn"]
        # Extract account ID from assumed role ARN: arn:aws:sts::ACCOUNT:assumed-role/...
        self.account_id = assumed_arn.split(":")[4]
        self.assumed_role_arn = assumed_arn

        session: _boto3.Session = boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=self.region,
        )

        # Cache until 10 min before credential expiry (50 min window)
        _SESSION_CACHE[ck] = (time.time() + 50 * 60, session)

        log.info(
            "sts.assume_role.success",
            role_arn=self.role_arn,
            account_id=self.account_id,
        )
        return session

    @classmethod
    def clear_cache(cls) -> None:
        """Flush the STS session cache — for use in tests only."""
        _SESSION_CACHE.clear()
