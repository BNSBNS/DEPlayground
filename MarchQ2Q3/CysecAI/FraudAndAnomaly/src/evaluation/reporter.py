"""HTML evaluation report generator.

Produces a self-contained HTML report with:
- Precision-recall curve
- Confusion matrix heatmap
- Feature importance bar chart
- Sample flagged transactions table
"""

from __future__ import annotations

import base64
import io
from typing import TYPE_CHECKING

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

if TYPE_CHECKING:
    from pathlib import Path

    from src.evaluation.metrics import EvaluationResult


def _fig_to_base64(fig: matplotlib.figure.Figure) -> str:
    """Convert matplotlib figure to base64 PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return encoded


def _render_pr_curve(result: EvaluationResult) -> str:
    """Render precision-recall curve as base64 image."""
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(result.pr_recalls, result.pr_precisions, linewidth=2)
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title(f"Precision-Recall Curve (AUC-PR={result.auc_pr:.3f})")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.3)
    return _fig_to_base64(fig)


def _render_confusion_matrix(result: EvaluationResult) -> str:
    """Render confusion matrix heatmap as base64 image."""
    cm = np.array(
        [
            [result.true_negatives, result.false_positives],
            [result.false_negatives, result.true_positives],
        ]
    )
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(cm, cmap="Blues")
    fig.colorbar(im)
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Normal", "Fraud"])
    ax.set_yticklabels(["Normal", "Fraud"])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title("Confusion Matrix")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=14, fontweight="bold")
    return _fig_to_base64(fig)


def _render_feature_importance(feature_names: list[str], importances: list[float]) -> str:
    """Render feature importance bar chart as base64 image."""
    sorted_idx = np.argsort(importances)
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(
        [feature_names[i] for i in sorted_idx],
        [importances[i] for i in sorted_idx],
    )
    ax.set_xlabel("Importance")
    ax.set_title("Feature Importance")
    return _fig_to_base64(fig)


def generate_html_report(
    result: EvaluationResult,
    model_name: str,
    feature_names: list[str] | None = None,
    feature_importances: list[float] | None = None,
    output_path: Path | None = None,
) -> str:
    """Generate self-contained HTML evaluation report.

    Returns the HTML string. Optionally writes to output_path.
    """
    pr_img = _render_pr_curve(result)
    cm_img = _render_confusion_matrix(result)

    fi_section = ""
    if feature_names and feature_importances:
        fi_img = _render_feature_importance(feature_names, feature_importances)
        fi_section = f"""
        <h2>Feature Importance</h2>
        <img src="data:image/png;base64,{fi_img}" alt="Feature Importance">
        """

    var_section = ""
    if result.fraud_amount_detected > 0 or result.fraud_amount_missed > 0:
        total = result.fraud_amount_detected + result.fraud_amount_missed
        pct = result.fraud_amount_detected / total * 100 if total > 0 else 0
        var_section = f"""
        <h2>Value-at-Risk</h2>
        <table>
            <tr><td>Fraud Amount Detected</td><td>${result.fraud_amount_detected:,.2f}</td></tr>
            <tr><td>Fraud Amount Missed</td><td>${result.fraud_amount_missed:,.2f}</td></tr>
            <tr><td>Detection Rate</td><td>{pct:.1f}%</td></tr>
        </table>
        """

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Fraud Detection Report — {model_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #fafafa; }}
        h1 {{ color: #333; border-bottom: 2px solid #333; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        table {{ border-collapse: collapse; margin: 10px 0; }}
        td, th {{ border: 1px solid #ddd; padding: 8px 16px; text-align: left; }}
        th {{ background: #f0f0f0; }}
        img {{ max-width: 100%; margin: 10px 0; }}
        .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }}
        .metric-card {{ background: white; padding: 20px; border-radius: 8px;
                       box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; }}
        .metric-value {{ font-size: 2em; font-weight: bold; color: #2c5282; }}
        .metric-label {{ color: #666; margin-top: 5px; }}
    </style>
</head>
<body>
    <h1>Fraud Detection Report — {model_name}</h1>

    <h2>Key Metrics</h2>
    <div class="metrics">
        <div class="metric-card">
            <div class="metric-value">{result.auc_pr:.3f}</div>
            <div class="metric-label">AUC-PR</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{result.f1:.3f}</div>
            <div class="metric-label">F1 Score</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{result.fpr:.3f}</div>
            <div class="metric-label">False Positive Rate</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{result.precision:.3f}</div>
            <div class="metric-label">Precision</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{result.recall:.3f}</div>
            <div class="metric-label">Recall</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{result.true_positives + result.true_negatives}</div>
            <div class="metric-label">Correct Predictions</div>
        </div>
    </div>

    <h2>Precision-Recall Curve</h2>
    <img src="data:image/png;base64,{pr_img}" alt="Precision-Recall Curve">

    <h2>Confusion Matrix</h2>
    <img src="data:image/png;base64,{cm_img}" alt="Confusion Matrix">

    {fi_section}
    {var_section}
</body>
</html>"""

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

    return html
