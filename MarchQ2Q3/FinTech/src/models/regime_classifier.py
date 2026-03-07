"""HMM-based market regime classifier (2 or 3 states, selected by BIC)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from hmmlearn.hmm import GaussianHMM

from src.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RegimeResult:
    """Fitted regime model with diagnostics."""

    model: GaussianHMM
    n_states: int
    bic: float
    states: np.ndarray
    transition_matrix: np.ndarray
    means: np.ndarray
    state_labels: list[str]


def fit_regime_model(
    features: np.ndarray,
    max_states: int = 3,
    n_iter: int = 200,
    random_state: int = 42,
) -> RegimeResult:
    """Fit HMM with 2 and 3 states, select by BIC.

    Args:
        features: (n_samples, n_features) array of stationary inputs
                  (e.g., log(VIX), diff(yield_curve), pct_change(rv))
        max_states: max number of states to try (2 or 3)
        n_iter: EM iterations
        random_state: for reproducibility

    Returns:
        RegimeResult with the best model
    """
    best: RegimeResult | None = None

    for n in range(2, max_states + 1):
        model = GaussianHMM(
            n_components=n,
            covariance_type="full",
            n_iter=n_iter,
            random_state=random_state,
        )
        model.fit(features)
        log_likelihood = model.score(features)
        n_params = n * n + n * features.shape[1] + n * features.shape[1] ** 2
        bic = -2 * log_likelihood + n_params * np.log(features.shape[0])

        states = model.predict(features)
        logger.info(
            "hmm_fit",
            n_states=n,
            bic=f"{bic:.1f}",
            log_likelihood=f"{log_likelihood:.1f}",
        )

        if best is None or bic < best.bic:
            # Label states by mean of first feature (ascending)
            order = np.argsort(model.means_[:, 0])
            labels = ["low_vol", "high_vol", "crisis"][:n]
            ordered_labels = [labels[np.where(order == i)[0][0]] for i in range(n)]

            best = RegimeResult(
                model=model,
                n_states=n,
                bic=bic,
                states=states,
                transition_matrix=model.transmat_,
                means=model.means_,
                state_labels=ordered_labels,
            )

    assert best is not None
    logger.info("hmm_selected", n_states=best.n_states, bic=f"{best.bic:.1f}")
    return best
