"""Tests for the benchmark suite."""

from __future__ import annotations

from src.benchmark.suite import BenchmarkReport, run_benchmark
from src.classifier.taxonomy import AttackType


class TestBenchmarkReport:
    def test_scorecard_contains_accuracy(self) -> None:
        report = BenchmarkReport(
            accuracy=0.92,
            per_class={"benign": {"precision": 0.95, "recall": 0.90, "f1": 0.92}},
            confusion_matrix=[[10, 1], [0, 9]],
            labels=["benign", "prompt_injection"],
        )
        card = report.scorecard()
        assert "92.00%" in card
        assert "benign" in card

    def test_scorecard_contains_all_classes(self) -> None:
        per_class = {t.value: {"precision": 0.9, "recall": 0.9, "f1": 0.9} for t in AttackType}
        report = BenchmarkReport(accuracy=0.9, per_class=per_class, confusion_matrix=[])
        card = report.scorecard()
        for attack in AttackType:
            assert attack.value in card


class TestRunBenchmark:
    def test_returns_benchmark_report(self) -> None:
        report = run_benchmark()
        assert isinstance(report, BenchmarkReport)

    def test_accuracy_in_range(self) -> None:
        report = run_benchmark()
        assert 0.0 <= report.accuracy <= 1.0

    def test_accuracy_above_threshold(self) -> None:
        report = run_benchmark()
        assert report.accuracy >= 0.80, f"Benchmark accuracy {report.accuracy:.2%} below 80%"

    def test_all_attack_types_in_per_class(self) -> None:
        report = run_benchmark()
        for attack in AttackType:
            assert attack.value in report.per_class

    def test_confusion_matrix_shape(self) -> None:
        report = run_benchmark()
        n = len(report.labels)
        assert len(report.confusion_matrix) == n
        assert all(len(row) == n for row in report.confusion_matrix)

    def test_labels_include_all_types(self) -> None:
        report = run_benchmark()
        for attack in AttackType:
            assert attack.value in report.labels

    def test_scorecard_renders(self) -> None:
        report = run_benchmark()
        card = report.scorecard()
        assert len(card) > 0
        assert "Accuracy" in card
