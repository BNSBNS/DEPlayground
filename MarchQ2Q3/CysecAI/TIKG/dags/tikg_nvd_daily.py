"""Airflow DAG — daily NVD CVE ingest into the TIKG knowledge graph."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DAG definition (only parsed when Airflow is present)
# ---------------------------------------------------------------------------
try:
    from airflow import DAG  # type: ignore[import-untyped]
    from airflow.operators.python import PythonOperator  # type: ignore[import-untyped]

    _AIRFLOW_AVAILABLE = True
except ImportError:
    _AIRFLOW_AVAILABLE = False

_DEFAULT_ARGS = {
    "owner": "tikg",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def ingest_nvd(**context: object) -> None:  # noqa: ARG001
    """Fetch the last 7 days of NVD CVEs and load into Neo4j."""
    from neo4j import AsyncGraphDatabase  # type: ignore[import-untyped]

    from src.config import TIKGSettings
    from src.graph.loader import GraphLoader
    from src.ingestion.nvd_client import NVDClient

    settings = TIKGSettings()
    now = datetime.utcnow()  # noqa: DTZ003
    start = now - timedelta(days=7)

    async def _run() -> None:
        driver = AsyncGraphDatabase.driver(
            settings.neo4j.uri,
            auth=(settings.neo4j.user, settings.neo4j.password),
        )
        async with NVDClient(settings.nvd) as client:
            cves = await client.fetch_all(pub_start_date=start, pub_end_date=now)
        loader = GraphLoader(driver, settings.neo4j.database)
        await loader.apply_schema()
        await loader.load_cve_batch(cves)
        await driver.close()
        logger.info("NVD ingest complete: %d CVEs", len(cves))

    asyncio.run(_run())


if _AIRFLOW_AVAILABLE:
    with DAG(
        dag_id="tikg_nvd_daily",
        description="Daily NVD CVE ingest into TIKG",
        schedule="0 2 * * *",  # 02:00 UTC daily
        start_date=datetime(2025, 1, 1),
        catchup=False,
        default_args=_DEFAULT_ARGS,
        tags=["tikg", "nvd", "cve"],
    ) as _nvd_dag:
        PythonOperator(
            task_id="ingest_nvd_cves",
            python_callable=ingest_nvd,
        )
