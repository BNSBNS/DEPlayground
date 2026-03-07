"""Tests for evaluation module (Phase 5).

Tests metrics computation, HTML report generation, and MLflow tracking.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    from pathlib import Path

from src.evaluation.metrics import EvaluationResult, evaluate
from src.evaluation.reporter import generate_html_report
from src.evaluation.tracker import ExperimentTracker


@pytest.fixture()
def sample_predictions() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Synthetic predictions for metrics testing."""
    rng = np.random.default_rng(42)
    y_true = np.array([0] * 90 + [1] * 10)
    y_scores = np.where(y_true == 1, rng.uniform(0.5, 1.0, 100), rng.uniform(0.0, 0.5, 100))
    y_pred = (y_scores >= 0.5).astype(int)
    amounts = rng.uniform(10, 1000, 100)
    return y_true, y_pred, y_scores, amounts


@pytest.fixture()
def sample_result(
    sample_predictions: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
) -> EvaluationResult:
    """Pre-computed evaluation result."""
    y_true, y_pred, y_scores, amounts = sample_predictions
    return evaluate(y_true, y_pred, y_scores, amounts)


class TestMetrics:
    """Evaluation metrics tests."""

    def test_evaluate_returns_result(self, sample_result: EvaluationResult) -> None:
        assert isinstance(sample_result, EvaluationResult)

    def test_auc_pr_range(self, sample_result: EvaluationResult) -> None:
        assert 0.0 <= sample_result.auc_pr <= 1.0

    def test_f1_range(self, sample_result: EvaluationResult) -> None:
        assert 0.0 <= sample_result.f1 <= 1.0

    def test_precision_range(self, sample_result: EvaluationResult) -> None:
        assert 0.0 <= sample_result.precision <= 1.0

    def test_recall_range(self, sample_result: EvaluationResult) -> None:
        assert 0.0 <= sample_result.recall <= 1.0

    def test_fpr_range(self, sample_result: EvaluationResult) -> None:
        assert 0.0 <= sample_result.fpr <= 1.0

    def test_confusion_matrix_sums(self, sample_result: EvaluationResult) -> None:
        total = (
            sample_result.true_positives
            + sample_result.false_positives
            + sample_result.true_negatives
            + sample_result.false_negatives
        )
        assert total == 100

    def test_pr_curve_populated(self, sample_result: EvaluationResult) -> None:
        assert len(sample_result.pr_precisions) > 0
        assert len(sample_result.pr_recalls) > 0
        assert len(sample_result.pr_thresholds) > 0

    def test_fraud_amount_positive(self, sample_result: EvaluationResult) -> None:
        assert sample_result.fraud_amount_detected >= 0
        assert sample_result.fraud_amount_missed >= 0

    def test_evaluate_without_amounts(self) -> None:
        y_true = np.array([0, 0, 1, 1])
        y_pred = np.array([0, 0, 1, 0])
        y_scores = np.array([0.1, 0.2, 0.8, 0.4])
        result = evaluate(y_true, y_pred, y_scores)
        assert result.fraud_amount_detected == 0.0
        assert result.fraud_amount_missed == 0.0
        assert result.f1 > 0.0


class TestReporter:
    """HTML report generation tests."""

    def test_generates_html(self, sample_result: EvaluationResult) -> None:
        html = generate_html_report(sample_result, "TestModel")
        assert "<html>" in html
        assert "TestModel" in html

    def test_contains_metrics(self, sample_result: EvaluationResult) -> None:
        html = generate_html_report(sample_result, "TestModel")
        assert "AUC-PR" in html
        assert "F1 Score" in html
        assert "Precision" in html

    def test_contains_images(self, sample_result: EvaluationResult) -> None:
        html = generate_html_report(sample_result, "TestModel")
        assert "data:image/png;base64," in html

    def test_with_feature_importance(self, sample_result: EvaluationResult) -> None:
        names = ["feat_a", "feat_b", "feat_c"]
        imps = [0.5, 0.3, 0.2]
        html = generate_html_report(
            sample_result, "TestModel", feature_names=names, feature_importances=imps
        )
        assert "Feature Importance" in html

    def test_writes_to_file(self, sample_result: EvaluationResult, tmp_path: Path) -> None:
        out = tmp_path / "report.html"
        generate_html_report(sample_result, "TestModel", output_path=out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "<html>" in content

    def test_value_at_risk_section(self, sample_result: EvaluationResult) -> None:
        html = generate_html_report(sample_result, "TestModel")
        assert "Value-at-Risk" in html
        assert "Detection Rate" in html


class TestTracker:
    """MLflow experiment tracker tests."""

    def test_creates_experiment(self, tmp_path: Path) -> None:
        tracker = ExperimentTracker(
            experiment_name="test-exp",
            tracking_uri=f"sqlite:///{tmp_path}/mlflow.db",
        )
        assert tracker.experiment_name == "test-exp"

    def test_log_run_returns_id(self, sample_result: EvaluationResult, tmp_path: Path) -> None:
        tracker = ExperimentTracker(
            experiment_name="test-log",
            tracking_uri=f"sqlite:///{tmp_path}/mlflow.db",
        )
        run_id = tracker.log_run(
            model_name="test-model",
            params={"max_depth": 5, "learning_rate": 0.1},
            result=sample_result,
        )
        assert isinstance(run_id, str)
        assert len(run_id) > 0

    def test_log_with_feature_importances(
        self, sample_result: EvaluationResult, tmp_path: Path
    ) -> None:
        tracker = ExperimentTracker(
            experiment_name="test-fi",
            tracking_uri=f"sqlite:///{tmp_path}/mlflow.db",
        )
        run_id = tracker.log_run(
            model_name="test-fi-model",
            params={"n_estimators": 100},
            result=sample_result,
            feature_importances={"amount_log": 0.5, "hour_of_day": 0.3},
        )
        assert len(run_id) > 0

    def test_log_with_artifacts(self, sample_result: EvaluationResult, tmp_path: Path) -> None:
        artifact = tmp_path / "report.html"
        artifact.write_text("<html>test</html>")
        tracker = ExperimentTracker(
            experiment_name="test-artifacts",
            tracking_uri=f"sqlite:///{tmp_path}/mlflow.db",
        )
        run_id = tracker.log_run(
            model_name="test-artifact-model",
            params={"epochs": 50},
            result=sample_result,
            artifacts=[artifact],
        )
        assert len(run_id) > 0

    def test_log_with_tags(self, sample_result: EvaluationResult, tmp_path: Path) -> None:
        tracker = ExperimentTracker(
            experiment_name="test-tags",
            tracking_uri=f"sqlite:///{tmp_path}/mlflow.db",
        )
        run_id = tracker.log_run(
            model_name="tagged-model",
            params={"batch_size": 256},
            result=sample_result,
            tags={"version": "v1.0", "dataset": "synthetic"},
        )
        assert len(run_id) > 0
