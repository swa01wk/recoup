"""
Account Scanner — identify cost-saving opportunities across an AWS account.

Credentials provided by the user are scoped to a boto3 session for the duration
of the scan and never written to any store or log.
"""

from .base import BaseScanner
from .finding import Finding, ScanRequest, ScanResult

__all__ = ["BaseScanner", "Finding", "ScanRequest", "ScanResult"]
