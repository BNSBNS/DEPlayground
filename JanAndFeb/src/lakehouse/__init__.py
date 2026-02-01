"""Unified Lakehouse Architecture module.

This module implements the Lakehouse pattern (Unified architecture) for the
Energy Trading Platform, combining the best of data lakes and data warehouses:

- ACID transactions on data lake storage
- Schema enforcement and evolution
- Time travel (query historical versions)
- Unified batch and streaming processing

Architecture Layers:
1. Bronze Layer: Raw data ingestion (append-only, no transformations)
2. Silver Layer: Cleaned, validated, deduplicated data
3. Gold Layer: Aggregated, business-level data (VWAP, LMP)

Technology Stack:
- Storage: MinIO (S3-compatible) / S3
- Table Format: Delta Lake (via delta-rs for Python)
- Processing: DuckDB (local) / Spark (production)
- Orchestration: Airflow (optional)

This is the recommended architecture over Lambda because:
1. Single codebase for batch and streaming
2. ACID guarantees for data consistency
3. Time travel for debugging and auditing
4. Schema evolution support
5. Better suited for energy market compliance (REMIT, MiFID II)

For Lambda architecture documentation, see docs/LAMBDA_ARCHITECTURE.md
"""

from src.lakehouse.bronze import BronzeLayer
from src.lakehouse.silver import SilverLayer
from src.lakehouse.gold import GoldLayer

__all__ = [
    "BronzeLayer",
    "SilverLayer",
    "GoldLayer",
]
