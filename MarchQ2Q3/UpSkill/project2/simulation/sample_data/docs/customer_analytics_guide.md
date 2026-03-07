# Customer Analytics Guide

## Key Metrics

- **Customer Lifetime Value (CLV)**: Total revenue attributed to a customer over their entire relationship. Calculated in customers_mart as the sum of all order totals.
- **Churn Rate**: Percentage of customers who have not placed an order in the last 90 days. Tracked in customer_cohorts.
- **Monthly Active Users (MAU)**: Customers with at least one session in the past 30 days.

## Cohort Analysis

The customer_cohorts model groups customers by their signup month and tracks retention over subsequent months. A customer is considered "retained" if they place at least one order in the given month.

## Data Freshness

Customer data refreshes daily at 06:00 UTC. The customers_mart table is rebuilt nightly. Session data has a 1-hour lag due to clickstream processing.
