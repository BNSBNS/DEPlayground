"""Airflow DAG — weekly MITRE ATT&CK + CISA KEV ingest."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

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
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}


def ingest_mitre(**context: object) -> None:  # noqa: ARG001
    """Fetch MITRE ATT&CK techniques and load into Neo4j."""
    from neo4j import AsyncGraphDatabase  # type: ignore[import-untyped]

    from src.config import TIKGSettings
    from src.graph.loader import GraphLoader
    from src.ingestion.mitre_client import MITREClient

    settings = TIKGSettings()

    async def _run() -> None:
        driver = AsyncGraphDatabase.driver(
            settings.neo4j.uri,
            auth=(settings.neo4j.user, settings.neo4j.password),
        )
        async with MITREClient() as client:
            techniques = await client.fetch_techniques()
        loader = GraphLoader(driver, settings.neo4j.database)
        for tech in techniques:
            await loader.load_technique(tech)
        await driver.close()
        logger.info("MITRE ingest complete: %d techniques", len(techniques))

    asyncio.run(_run())


def ingest_kev(**context: object) -> None:  # noqa: ARG001
    """Fetch CISA KEV catalog and load into Neo4j."""
    from neo4j import AsyncGraphDatabase  # type: ignore[import-untyped]

    from src.config import TIKGSettings
    from src.graph.loader import GraphLoader
    from src.ingestion.kev_client import KEVClient

    settings = TIKGSettings()

    async def _run() -> None:
        driver = AsyncGraphDatabase.driver(
            settings.neo4j.uri,
            auth=(settings.neo4j.user, settings.neo4j.password),
        )
        async with KEVClient() as client:
            entries = await client.fetch_all()
        loader = GraphLoader(driver, settings.neo4j.database)
        for kev in entries:
            await loader.load_kev(kev)
        await driver.close()
        logger.info("KEV ingest complete: %d entries", len(entries))

    asyncio.run(_run())


if _AIRFLOW_AVAILABLE:
    with DAG(
        dag_id="tikg_mitre_kev_weekly",
        description="Weekly MITRE ATT&CK + CISA KEV ingest into TIKG",
        schedule="0 3 * * 1",  # 03:00 UTC every Monday
        start_date=datetime(2025, 1, 1),
        catchup=False,
        default_args=_DEFAULT_ARGS,
        tags=["tikg", "mitre", "kev"],
    ) as _mitre_dag:
        _t_mitre = PythonOperator(
            task_id="ingest_mitre_techniques",
            python_callable=ingest_mitre,
        )
        _t_kev = PythonOperator(
            task_id="ingest_cisa_kev",
            python_callable=ingest_kev,
        )
        _t_mitre >> _t_kev
