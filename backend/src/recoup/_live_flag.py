"""
Thin helper to check whether real AWS resources are configured, without
importing the full settings object at module level (prevents circular imports
in the tools layer).
"""

from __future__ import annotations


def recoup_live_aws_enabled() -> bool:
    """Return True when real AWS resources are configured."""
    from .config import settings  # local import — safe, no circular dep

    return settings.live_aws_enabled
