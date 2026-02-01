"""Data quality module for the Energy Trading Platform.

This module provides data quality checks and metrics using a lightweight
approach suitable for a learning platform. It demonstrates the concepts
of data quality without the full overhead of enterprise governance tools.

Components:
- expectations: Great Expectations-style validation rules
- metrics: Prometheus metrics for quality monitoring
- checks: Quality check implementations

For production/enterprise use, consider:
- Great Expectations with a full expectation store
- Apache Atlas for data lineage
- DataHub or Amundsen for data cataloging
- Monte Carlo or similar for data observability
"""

from src.quality.checks import QualityChecker, QualityReport
from src.quality.metrics import (
    record_quality_check,
    record_validation_failure,
)

__all__ = [
    "QualityChecker",
    "QualityReport",
    "record_quality_check",
    "record_validation_failure",
]
