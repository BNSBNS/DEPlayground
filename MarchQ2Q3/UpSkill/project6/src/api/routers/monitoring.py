from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/freshness")
async def check_freshness(
    features: str = Query(default="", description="Comma-separated feature names"),
) -> dict[str, Any]:
    from src.api.main import get_freshness_monitor, get_catalog

    catalog = get_catalog()
    monitor = get_freshness_monitor()

    if features:
        feature_names = [f.strip() for f in features.split(",")]
    else:
        all_features = await catalog.list_features()
        feature_names = [f.name for f in all_features]

    slas: dict[str, int] = {}
    for fname in feature_names:
        feat = await catalog.get_feature(fname)
        slas[fname] = feat.freshness_sla_minutes if feat else 60

    results = await monitor.check_all(slas)
    return {
        "freshness": [r.to_dict() for r in results],
        "count": len(results),
    }


@router.get("/drift")
async def check_drift() -> dict[str, Any]:
    # Drift detection requires reference + current data; return placeholder
    return {
        "message": "Use POST /monitoring/drift with reference and current data",
        "drift_results": [],
    }


@router.get("/stats/{feature_name}")
async def get_feature_stats(feature_name: str) -> dict[str, Any]:
    from src.api.main import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM feature_stats
            WHERE feature_name = $1
            ORDER BY window_end DESC
            LIMIT 10
            """,
            feature_name,
        )

    stats = []
    for r in rows:
        stats.append({
            "feature_name": r["feature_name"],
            "window_start": r["window_start"].isoformat(),
            "window_end": r["window_end"].isoformat(),
            "count": r["count"],
            "null_count": r["null_count"],
            "null_pct": r["null_pct"],
            "mean": r["mean"],
            "stddev": r["stddev"],
            "min": r["min_val"],
            "max": r["max_val"],
            "p50": r["p50"],
            "p95": r["p95"],
        })

    return {"feature_name": feature_name, "stats": stats}
