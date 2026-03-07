"""Attack classifier — TF-IDF + Logistic Regression for LLM attack detection."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any, Self

import joblib
import mlflow
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

from src.classifier.dataset import LabeledSample, build_dataset
from src.classifier.taxonomy import AttackType

if TYPE_CHECKING:
    from pathlib import Path


class ClassifierMetrics(BaseModel):
    """Evaluation metrics from classifier training."""

    accuracy: float
    per_class: dict[str, dict[str, float]]


class BaseDetector(abc.ABC):
    """Abstract base for attack detectors."""

    @abc.abstractmethod
    def train(self, samples: list[LabeledSample]) -> ClassifierMetrics: ...

    @abc.abstractmethod
    def predict(self, text: str) -> tuple[AttackType, float]: ...

    @abc.abstractmethod
    def save(self, path: Path) -> None: ...

    @classmethod
    @abc.abstractmethod
    def load(cls, path: Path) -> Self: ...


class AttackClassifier(BaseDetector):
    """TF-IDF + Logistic Regression attack classifier."""

    MODEL_FILE = "classifier.joblib"

    def __init__(self) -> None:
        self._vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=20000,
            sublinear_tf=True,
        )
        self._model = LogisticRegression(
            max_iter=1000,
            C=1.0,
            class_weight="balanced",
        )
        self._trained: bool = False

    def train(self, samples: list[LabeledSample]) -> ClassifierMetrics:
        texts = [s.text for s in samples]
        labels = [s.label for s in samples]

        x_train, x_val, y_train, y_val = train_test_split(
            texts, labels, test_size=0.2, random_state=42, stratify=labels
        )
        x_train_vec = self._vectorizer.fit_transform(x_train)
        x_val_vec = self._vectorizer.transform(x_val)
        self._model.fit(x_train_vec, y_train)
        self._trained = True

        y_pred = self._model.predict(x_val_vec)
        report: dict[str, Any] = classification_report(
            y_val, y_pred, output_dict=True, zero_division=0
        )

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
        accuracy = float(report["accuracy"])
        result = ClassifierMetrics(accuracy=accuracy, per_class=per_class)

        mlflow.set_experiment("attack-classifier")
        with mlflow.start_run():
            mlflow.log_param("model_type", "LogisticRegression")
            mlflow.log_param("ngram_range", "(1,2)")
            mlflow.log_param("max_features", 20000)
            mlflow.log_param("train_size", len(x_train))
            mlflow.log_param("val_size", len(x_val))
            mlflow.log_metric("accuracy", accuracy)
            for metric_label, metric_vals in per_class.items():
                mlflow.log_metric(f"{metric_label}_precision", metric_vals["precision"])
                mlflow.log_metric(f"{metric_label}_recall", metric_vals["recall"])
                mlflow.log_metric(f"{metric_label}_f1", metric_vals["f1"])

        return result

    def predict(self, text: str) -> tuple[AttackType, float]:
        if not self._trained:
            msg = "Classifier not trained. Call train() first."
            raise RuntimeError(msg)
        vec = self._vectorizer.transform([text])
        label = str(self._model.predict(vec)[0])
        proba = float(self._model.predict_proba(vec).max())
        return AttackType(label), proba

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {"vectorizer": self._vectorizer, "model": self._model},
            path / self.MODEL_FILE,
        )

    @classmethod
    def load(cls, path: Path) -> Self:
        data: dict[str, Any] = joblib.load(path / cls.MODEL_FILE)
        obj = cls()
        obj._vectorizer = data["vectorizer"]
        obj._model = data["model"]
        obj._trained = True
        return obj


def train_classifier(
    model_dir: Path | None = None,
) -> tuple[AttackClassifier, ClassifierMetrics]:
    """Train on the full dataset and optionally save the model."""
    samples = build_dataset()
    classifier = AttackClassifier()
    metrics = classifier.train(samples)
    if model_dir is not None:
        classifier.save(model_dir)
    return classifier, metrics
