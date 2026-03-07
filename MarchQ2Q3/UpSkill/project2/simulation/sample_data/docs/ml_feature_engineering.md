# ML Feature Engineering

## Churn Prediction Features

The churn_prediction_features model generates features for our customer churn prediction model. Features are computed from customers_mart and session data.

### Features

- **days_since_last_order**: Calendar days between now and the customer's most recent order date. Higher values indicate higher churn risk.
- **order_frequency**: Average orders per month over the customer's lifetime.
- **avg_order_value**: Mean order total across all customer orders.
- **session_recency**: Days since the customer's last recorded session.
- **page_view_trend**: Slope of a linear regression over the customer's weekly page views for the past 8 weeks. Negative values indicate declining engagement.

### Refresh Schedule

Features are recomputed daily at 08:00 UTC after all upstream mart tables have been refreshed.

### Model Performance

The churn prediction model achieves 82% AUC-ROC on the holdout set. Feature importance (by SHAP values): days_since_last_order > session_recency > page_view_trend > order_frequency > avg_order_value.
