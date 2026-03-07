"""XGBoost fraud classifier.

Supervised model with automatic class weighting for imbalanced data.
Hyperparameters selected via 3-fold stratified CV on F1 score.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import xgboost as xgb
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold

from src.models.base import BaseDetector, Explanation


class XGBoostDetector(BaseDetector):
    """Supervised fraud detection via XGBoost with class weight balancing."""

    def __init__(self, random_state: int = 42, n_cv_folds: int = 3) -> None:
        self._random_state = random_state
        self._n_cv_folds = n_cv_folds
        self._model: xgb.XGBClassifier | None = None
        self._best_params: dict[str, Any] = {}
        self._threshold: float = 0.5
        self._train_mean: np.ndarray | None = None
        self._train_std: np.ndarray | None = None

    def fit(self, X: np.ndarray, y: np.ndarray | None = None) -> None:
        """Train with 3-fold CV hyperparameter search and class weighting."""
        if y is None:
            msg = "XGBoost requires labels (y)"
            raise ValueError(msg)

        n_pos = int(np.sum(y == 1))
        n_neg = int(np.sum(y == 0))
        scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

        self._train_mean = np.array(X.mean(axis=0))
        self._train_std = np.array(X.std(axis=0))
        self._train_std[self._train_std < 1e-10] = 1.0

        self._best_params = self._cv_search(X, y, scale_pos_weight)
        self._model = xgb.XGBClassifier(
            **self._best_params,
            scale_pos_weight=scale_pos_weight,
            random_state=self._random_state,
            eval_metric="logloss",
            verbosity=0,
        )
        self._model.fit(X, y)

        # Optimize classification threshold for F1 on training data
        self._threshold = self._find_optimal_threshold(X, y)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Binary predictions using optimized threshold."""
        proba = self.score(X)
        result: np.ndarray = (proba >= self._threshold).astype(int)
        return result

    def score(self, X: np.ndarray) -> np.ndarray:
        """Fraud probability from predict_proba."""
        assert self._model is not None
        proba: np.ndarray = self._model.predict_proba(X)
        return proba[:, 1]

    def explain(self, X: np.ndarray, feature_names: list[str]) -> list[Explanation]:
        """Top 3 features by importance-weighted deviation from training mean."""
        assert self._model is not None
        assert self._train_mean is not None and self._train_std is not None

        importances: np.ndarray = self._model.feature_importances_
        deviations = np.abs(X - self._train_mean) / self._train_std
        contributions = deviations * importances

        results: list[Explanation] = []
        for i in range(X.shape[0]):
            top_idx = np.argsort(contributions[i])[-3:][::-1]
            results.append([(feature_names[j], float(contributions[i, j])) for j in top_idx])
        return results

    @property
    def best_params(self) -> dict[str, Any]:
        """Best hyperparameters found during CV search."""
        return dict(self._best_params)

    def _cv_search(self, X: np.ndarray, y: np.ndarray, scale_pos_weight: float) -> dict[str, Any]:
        """3-fold stratified CV grid search optimizing F1 on fraud class."""
        param_grid: list[dict[str, Any]] = [
            {
                "max_depth": d,
                "learning_rate": lr,
                "n_estimators": n,
                "min_child_weight": mcw,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
            }
            for d in [4, 6]
            for lr in [0.05, 0.1]
            for n in [200, 400]
            for mcw in [1, 3]
        ]
        skf = StratifiedKFold(
            n_splits=self._n_cv_folds, shuffle=True, random_state=self._random_state
        )

        best_f1 = -1.0
        best_params: dict[str, Any] = param_grid[0]

        for params in param_grid:
            fold_scores: list[float] = []
            for train_idx, val_idx in skf.split(X, y):
                clf = xgb.XGBClassifier(
                    **params,
                    scale_pos_weight=scale_pos_weight,
                    random_state=self._random_state,
                    eval_metric="logloss",
                    verbosity=0,
                )
                clf.fit(X[train_idx], y[train_idx])
                y_pred: np.ndarray = clf.predict(X[val_idx])
                fold_scores.append(float(f1_score(y[val_idx], y_pred)))

            mean_f1 = float(np.mean(fold_scores))
            if mean_f1 > best_f1:
                best_f1 = mean_f1
                best_params = params

        return best_params

    def _find_optimal_threshold(self, X: np.ndarray, y: np.ndarray) -> float:
        """Find the probability threshold that maximizes F1 on training data."""
        proba = self.score(X)
        best_f1 = 0.0
        best_threshold = 0.5
        for t in np.arange(0.1, 0.9, 0.05):
            preds = (proba >= t).astype(int)
            f1 = float(f1_score(y, preds))
            if f1 > best_f1:
                best_f1 = f1
                best_threshold = float(t)
        return best_threshold
