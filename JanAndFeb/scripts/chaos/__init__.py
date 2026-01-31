"""Chaos Testing Framework for Data Pipeline Resilience.

This module provides tools to simulate common issues in streaming and batch
data pipelines, following SWE and Data Engineering best practices.

Issue Categories:
- Streaming: Poison pills, schema drift, duplicates, late events
- Batch: Corrupt files, encoding issues, schema changes, empty files

Patterns Used:
- Factory Pattern: Issue generators
- Strategy Pattern: Different simulation scenarios
- Observer Pattern: Event tracking and reporting
"""

__version__ = "1.0.0"
