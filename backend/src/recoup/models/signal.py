"""Incident signal — normalized input from EventBridge or replay adapter."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class IncidentSignal(BaseModel):
    source: Literal["aws_health", "cost_anomaly", "optimization", "replay"]
    event_id: str
    service: str
    region: str
    start: datetime
    end: datetime
    affected_resource_ids: list[str]
    raw_ref: str = Field(description="S3 URI of raw event; never the raw event content itself")
    replay: bool = False
