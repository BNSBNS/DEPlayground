"""Evaluation metrics for fraud detection models.

Primary metric: AUC-PR (appropriate for imbalanced data).
Also computes F1, precision, recall, FPR, and value-at-risk.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True)
class EvaluationResult:
    """Container for all evaluation metrics."""

    auc_pr: float
    f1: float
    precision: float
    recall: float
    fpr: float
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    fraud_amount_detected: float
    fraud_amount_missed: float
    pr_precisions: list[float]
    pr_recalls: list[float]
    pr_thresholds: list[float]


def evaluate(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_scores: np.ndarray,
    amounts: np.ndarray | None = None,
) -> EvaluationResult:
    """Compute all evaluation metrics.

    Args:
        y_true: Ground truth binary labels.
        y_pred: Predicted binary labels.
        y_scores: Continuous anomaly/fraud scores.
        amounts: Transaction amounts for value-at-risk calculation.
    """
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

    pr_prec, pr_rec, pr_thresh = precision_recall_curve(y_true, y_scores)

    # Value-at-risk: how much fraud amount was caught vs missed
    fraud_detected = 0.0
    fraud_missed = 0.0
    if amounts is not None:
        fraud_mask = y_true == 1
        fraud_detected = float(amounts[fraud_mask & (y_pred == 1)].sum())
        fraud_missed = float(amounts[fraud_mask & (y_pred == 0)].sum())

    return EvaluationResult(
        auc_pr=float(average_precision_score(y_true, y_scores)),
        f1=float(f1_score(y_true, y_pred)),
        precision=float(precision_score(y_true, y_pred)),
        recall=float(recall_score(y_true, y_pred)),
        fpr=fpr,
        true_positives=int(tp),
        false_positives=int(fp),
        true_negatives=int(tn),
        false_negatives=int(fn),
        fraud_amount_detected=fraud_detected,
        fraud_amount_missed=fraud_missed,
        pr_precisions=pr_prec.tolist(),
        pr_recalls=pr_rec.tolist(),
        pr_thresholds=pr_thresh.tolist(),
    )
