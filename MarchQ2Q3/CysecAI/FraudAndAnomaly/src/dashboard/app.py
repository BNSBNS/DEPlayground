"""Streamlit fraud detection dashboard.

Pages: Transaction Feed, Flagged Details, Fraud Trends, Model Performance.
Run: streamlit run src/dashboard/app.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.metrics import average_precision_score, f1_score, precision_recall_curve
from sklearn.model_selection import train_test_split

from src.config import GeneratorSettings
from src.data.generator import TransactionGenerator
from src.features.pipeline import FeaturePipeline
from src.models.autoencoder import AutoencoderDetector
from src.models.ensemble import EnsembleDetector
from src.models.isolation_forest import IsolationForestDetector
from src.models.xgboost_model import XGBoostDetector

if TYPE_CHECKING:
    from src.models.base import BaseDetector


def main() -> None:
    """Streamlit app entry point."""
    st.set_page_config(page_title="Fraud Detection Dashboard", layout="wide")
    st.title("Fraud & Anomaly Detection Dashboard")

    # Sidebar controls
    st.sidebar.header("Controls")
    n_transactions = st.sidebar.slider("Transactions", 1000, 10000, 5000, 1000)
    threshold = st.sidebar.slider("Detection Threshold", 0.1, 0.9, 0.5, 0.05)
    seed = st.sidebar.number_input("Random Seed", value=42, min_value=0)

    # Load/train models (cached)
    data = _load_data(n_transactions, int(seed))
    df, X_train, X_test, y_train, y_test, features = data

    models = _train_models(X_train, y_train, int(seed))
    ensemble = models["ensemble"]

    # Score test set
    scores = ensemble.score(X_test)
    preds = (scores >= threshold).astype(int)

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Transaction Feed", "Flagged Details", "Fraud Trends", "Model Performance"]
    )

    with tab1:
        _render_transaction_feed(X_test, y_test, scores, preds, features)

    with tab2:
        _render_flagged_details(X_test, y_test, scores, preds, features, ensemble)

    with tab3:
        _render_fraud_trends(df)

    with tab4:
        _render_model_performance(y_test, scores, preds, models, X_test)


@st.cache_data
def _load_data(
    n_transactions: int, seed: int
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Generate and prepare data."""
    settings = GeneratorSettings(num_transactions=n_transactions, seed=seed, num_users=500)
    txs = TransactionGenerator(settings).generate()
    pipeline = FeaturePipeline()
    df = pipeline.run(txs)
    features = list(pipeline.feature_columns)
    X = df[features].values.astype(np.float64)
    y = df["is_fraud"].astype(int).values
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y
    )
    return df, X_train, X_test, y_train, y_test, features


@st.cache_resource
def _train_models(
    _X_train: np.ndarray, _y_train: np.ndarray, seed: int
) -> dict[str, IsolationForestDetector | XGBoostDetector | EnsembleDetector]:
    """Train all models (cached)."""
    iforest = IsolationForestDetector(random_state=seed)
    iforest.fit(_X_train)

    xgboost = XGBoostDetector(random_state=seed)
    xgboost.fit(_X_train, _y_train)

    autoenc = AutoencoderDetector(epochs=30, random_state=seed)
    autoenc.fit(_X_train, _y_train)

    ensemble = EnsembleDetector(detectors=[iforest, xgboost, autoenc], weights=[0.2, 0.5, 0.3])
    ensemble.fit(_X_train, _y_train)

    return {"iforest": iforest, "xgboost": xgboost, "ensemble": ensemble}


def _render_transaction_feed(
    X_test: np.ndarray,
    y_test: np.ndarray,
    scores: np.ndarray,
    preds: np.ndarray,
    features: list[str],
) -> None:
    """Live transaction feed with color-coded risk."""
    st.subheader("Transaction Feed")

    # Build display DataFrame
    n_test = len(y_test)
    feed = pd.DataFrame(
        {
            "Score": scores,
            "Predicted": ["Fraud" if p else "Normal" for p in preds],
            "Actual": ["Fraud" if a else "Normal" for a in y_test],
            "Risk": pd.cut(
                scores,
                bins=[0, 0.3, 0.5, 0.7, 1.0],
                labels=["Low", "Medium", "High", "Critical"],
            ),
        },
        index=range(n_test),
    )

    # Add key features
    for i, f in enumerate(features[:5]):
        feed[f] = X_test[:, i]

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Transactions", n_test)
    col2.metric("Flagged", int(preds.sum()))
    col3.metric("Avg Score", f"{scores.mean():.3f}")
    col4.metric("Flag Rate", f"{preds.mean():.1%}")

    st.dataframe(
        feed.style.apply(
            lambda row: (
                ["background-color: #ffcccc" if row["Risk"] in ("High", "Critical") else ""]
                * len(row)
            ),
            axis=1,
        ),
        use_container_width=True,
        height=400,
    )


def _render_flagged_details(
    X_test: np.ndarray,
    y_test: np.ndarray,
    scores: np.ndarray,
    preds: np.ndarray,
    features: list[str],
    ensemble: BaseDetector,
) -> None:
    """Detailed view of flagged transactions."""
    st.subheader("Flagged Transaction Details")

    flagged_idx = np.where(preds == 1)[0]
    if len(flagged_idx) == 0:
        st.info("No transactions flagged at current threshold.")
        return

    selected = st.selectbox("Select flagged transaction", flagged_idx)
    if selected is not None:
        idx = int(selected)
        st.write(f"**Score:** {scores[idx]:.4f}")
        st.write(f"**Actual:** {'Fraud' if y_test[idx] == 1 else 'Normal'}")

        # Explanation
        explanation = ensemble.explain(X_test[idx : idx + 1], features)[0]
        st.write("**Top Contributing Features:**")
        exp_df = pd.DataFrame(explanation, columns=["Feature", "Contribution"])
        st.bar_chart(exp_df.set_index("Feature"))

        # Feature values
        st.write("**Feature Values:**")
        feat_df = pd.DataFrame(
            {"Feature": features, "Value": X_test[idx]},
        )
        st.dataframe(feat_df, use_container_width=True)


def _render_fraud_trends(df: pd.DataFrame) -> None:
    """Fraud trend charts."""
    st.subheader("Fraud Trends")

    # Hourly fraud distribution
    df_copy = df.copy()
    df_copy["hour"] = pd.to_datetime(df_copy["timestamp"]).dt.hour

    hourly = df_copy.groupby("hour")["is_fraud"].agg(["sum", "count"]).reset_index()
    hourly["fraud_rate"] = hourly["sum"] / hourly["count"]

    fig_hourly = px.bar(
        hourly,
        x="hour",
        y="fraud_rate",
        title="Fraud Rate by Hour of Day",
        labels={"hour": "Hour", "fraud_rate": "Fraud Rate"},
    )
    st.plotly_chart(fig_hourly, use_container_width=True)

    # Amount distribution
    fig_amount = px.histogram(
        df_copy,
        x="amount",
        color="is_fraud",
        nbins=50,
        title="Amount Distribution by Class",
        labels={"amount": "Amount", "is_fraud": "Is Fraud"},
        barmode="overlay",
        opacity=0.7,
    )
    st.plotly_chart(fig_amount, use_container_width=True)


def _render_model_performance(
    y_test: np.ndarray,
    scores: np.ndarray,
    preds: np.ndarray,
    models: dict[str, IsolationForestDetector | XGBoostDetector | EnsembleDetector],
    X_test: np.ndarray,
) -> None:
    """Model performance metrics and charts."""
    st.subheader("Model Performance")

    # Metrics
    f1 = float(f1_score(y_test, preds))
    auc_pr = float(average_precision_score(y_test, scores))

    col1, col2, col3 = st.columns(3)
    col1.metric("F1 Score", f"{f1:.3f}")
    col2.metric("AUC-PR", f"{auc_pr:.3f}")
    col3.metric("Flagged Count", int(preds.sum()))

    # PR Curve
    prec, rec, _ = precision_recall_curve(y_test, scores)
    fig_pr = go.Figure()
    fig_pr.add_trace(go.Scatter(x=rec, y=prec, mode="lines", name="Ensemble"))

    # Add individual model PR curves
    for name, model in models.items():
        if name != "ensemble":
            m_scores = model.score(X_test)
            m_prec, m_rec, _ = precision_recall_curve(y_test, m_scores)
            fig_pr.add_trace(go.Scatter(x=m_rec, y=m_prec, mode="lines", name=name))

    fig_pr.update_layout(
        title="Precision-Recall Curves",
        xaxis_title="Recall",
        yaxis_title="Precision",
    )
    st.plotly_chart(fig_pr, use_container_width=True)

    # Score distribution
    fig_dist = px.histogram(
        x=scores,
        color=["Fraud" if y else "Normal" for y in y_test],
        nbins=50,
        title="Score Distribution by Class",
        labels={"x": "Fraud Score", "color": "Class"},
        barmode="overlay",
        opacity=0.7,
    )
    st.plotly_chart(fig_dist, use_container_width=True)


if __name__ == "__main__":
    main()
