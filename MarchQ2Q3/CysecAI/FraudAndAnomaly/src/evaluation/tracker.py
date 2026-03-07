"""MLflow experiment tracking for fraud detection models.

Logs hyperparameters, metrics, feature importance, and model artifacts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import mlflow

if TYPE_CHECKING:
    from pathlib import Path

    from src.evaluation.metrics import EvaluationResult


class ExperimentTracker:
    """MLflow-backed experiment tracker."""

    def __init__(self, experiment_name: str = "fraud-detection", tracking_uri: str = "") -> None:
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)
        self._experiment_name = experiment_name

    def log_run(
        self,
        model_name: str,
        params: dict[str, Any],
        result: EvaluationResult,
        feature_importances: dict[str, float] | None = None,
        artifacts: list[Path] | None = None,
        tags: dict[str, str] | None = None,
    ) -> str:
        """Log a complete training run to MLflow.

        Returns the MLflow run ID.
        """
        with mlflow.start_run(run_name=model_name) as run:
            # Tags
            mlflow.set_tag("model_type", model_name)
            if tags:
                for k, v in tags.items():
                    mlflow.set_tag(k, v)

            # Parameters
            mlflow.log_params(params)

            # Metrics
            mlflow.log_metrics(
                {
                    "auc_pr": result.auc_pr,
                    "f1": result.f1,
                    "precision": result.precision,
                    "recall": result.recall,
                    "fpr": result.fpr,
                    "true_positives": float(result.true_positives),
                    "false_positives": float(result.false_positives),
                    "fraud_amount_detected": result.fraud_amount_detected,
                    "fraud_amount_missed": result.fraud_amount_missed,
                }
            )

            # Feature importances as metrics
            if feature_importances:
                for fname, imp in feature_importances.items():
                    mlflow.log_metric(f"importance_{fname}", imp)

            # Artifacts (HTML reports, model files, etc.)
            if artifacts:
                for path in artifacts:
                    if path.exists():
                        mlflow.log_artifact(str(path))

            run_id: str = run.info.run_id
            return run_id

    @property
    def experiment_name(self) -> str:
        """Current experiment name."""
        return self._experiment_name
