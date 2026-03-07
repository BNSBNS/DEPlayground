"""Fraud alert emitter.

Converts fraud predictions into SecurityAlert format and emits to Kafka.
Uses the shared AlertEmitter from cysec-shared for actual Kafka publishing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from cysec_shared.models.alerts import SecurityAlert

if TYPE_CHECKING:
    import numpy as np

SOURCE_PROJECT = "FraudAndAnomaly"
RULE_ID = "fraud-detection-ensemble"


def build_fraud_alert(
    transaction_id: str,
    user_id: str,
    score: float,
    explanation: list[tuple[str, float]],
    ip_address: str | None = None,
) -> SecurityAlert:
    """Build a SecurityAlert from a fraud prediction.

    Args:
        transaction_id: The flagged transaction ID.
        user_id: The user who made the transaction.
        score: Fraud probability/anomaly score (0-1).
        explanation: Top contributing features with scores.
        ip_address: Source IP if available.
    """
    severity = _score_to_severity(score)
    top_features = ", ".join(f"{name} ({val:.2f})" for name, val in explanation[:3])

    return SecurityAlert(
        source_project=SOURCE_PROJECT,
        rule_id=RULE_ID,
        severity=severity,
        title=f"Suspicious transaction detected: {transaction_id}",
        description=(
            f"Transaction {transaction_id} by user {user_id} flagged with "
            f"fraud score {score:.3f}. Top features: {top_features}."
        ),
        mitre_technique_id="T1078",
        mitre_tactic="Initial Access",
        cia_impact=["integrity"],
        evidence=_build_evidence(transaction_id, user_id, score, explanation),
        affected_asset=f"user:{user_id}",
        source_ip=ip_address,
        user=user_id,
        recommendations=[
            "Review transaction details and user activity",
            "Consider temporary account hold pending investigation",
            "Check for related transactions from same IP/device",
        ],
    )


def build_alerts_from_predictions(
    transaction_ids: list[str],
    user_ids: list[str],
    scores: np.ndarray,
    predictions: np.ndarray,
    explanations: list[list[tuple[str, float]]],
    ip_addresses: list[str | None] | None = None,
    threshold: float = 0.5,
) -> list[SecurityAlert]:
    """Build alerts for all flagged transactions in a batch.

    Only creates alerts for transactions where prediction == 1
    or score >= threshold.
    """
    alerts: list[SecurityAlert] = []
    ips = ip_addresses or [None] * len(transaction_ids)

    for i, (tid, uid, score, pred) in enumerate(
        zip(transaction_ids, user_ids, scores, predictions, strict=True)
    ):
        if pred == 1 or float(score) >= threshold:
            alerts.append(build_fraud_alert(tid, uid, float(score), explanations[i], ips[i]))
    return alerts


_Severity = Literal["critical", "high", "medium", "low", "info"]


def _score_to_severity(score: float) -> _Severity:
    """Map fraud score to alert severity."""
    if score >= 0.9:
        return "critical"
    if score >= 0.7:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _build_evidence(
    transaction_id: str,
    user_id: str,
    score: float,
    explanation: list[tuple[str, float]],
) -> dict[str, Any]:
    """Build evidence payload for the alert."""
    return {
        "transaction_id": transaction_id,
        "user_id": user_id,
        "fraud_score": round(score, 4),
        "top_features": [
            {"feature": name, "contribution": round(val, 4)} for name, val in explanation[:3]
        ],
    }
