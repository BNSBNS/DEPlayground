"""Classifier benchmark suite — per-class metrics and scorecard."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

from src.classifier.dataset import build_dataset
from src.classifier.detector import AttackClassifier

if TYPE_CHECKING:
    from src.classifier.dataset import LabeledSample


@dataclass
class BenchmarkReport:
    """Results from a classifier benchmark run."""

    accuracy: float
    per_class: dict[str, dict[str, float]]
    confusion_matrix: list[list[int]]
    labels: list[str] = field(default_factory=list)

    def scorecard(self) -> str:
        """Return a formatted text scorecard."""
        lines = [
            "=" * 62,
            "  LLM Attack Classifier — Benchmark Scorecard",
            "=" * 62,
            f"  Overall Accuracy : {self.accuracy:.2%}",
            "",
            f"  {'Class':<28} {'Precision':>9} {'Recall':>9} {'F1':>9}",
            "  " + "-" * 58,
        ]
        for cls, m in sorted(self.per_class.items()):
            lines.append(f"  {cls:<28} {m['precision']:>9.2%} {m['recall']:>9.2%} {m['f1']:>9.2%}")
        lines.append("=" * 62)
        return "\n".join(lines)


def run_benchmark(samples: list[LabeledSample] | None = None) -> BenchmarkReport:
    """Train and evaluate the classifier; return a BenchmarkReport."""
    if samples is None:
        samples = build_dataset()

    texts = [s.text for s in samples]
    labels = [s.label for s in samples]
    unique_labels = sorted(set(labels))

    _, x_val, _, y_val = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )

    clf = AttackClassifier()
    clf.train(samples)

    y_pred = [clf.predict(text)[0].value for text in x_val]

    report: dict[str, Any] = classification_report(y_val, y_pred, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_val, y_pred, labels=unique_labels)

    _aggregate = {"accuracy", "macro avg", "weighted avg"}
    per_class = {
        cls_label: {
            "precision": float(cls_m["precision"]),
            "recall": float(cls_m["recall"]),
            "f1": float(cls_m["f1-score"]),
        }
        for cls_label, cls_m in report.items()
        if cls_label not in _aggregate
    }

    return BenchmarkReport(
        accuracy=float(report["accuracy"]),
        per_class=per_class,
        confusion_matrix=cm.tolist(),
        labels=unique_labels,
    )
