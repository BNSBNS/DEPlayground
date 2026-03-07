# Data Quality Standards

## Freshness SLAs

| Dataset | Max Staleness | Check Frequency |
|---------|--------------|-----------------|
| Raw tables | 2 hours | Every 30 min |
| Staging models | 3 hours | Every hour |
| Mart tables | 6 hours | Every hour |
| Metrics tables | 12 hours | Every 2 hours |

## Completeness Requirements

- **orders_mart**: NULL rate must be below 1% for order_total and customer_id
- **customers_mart**: Email must be non-null for 99%+ of records
- **products_mart**: Category must always be populated

## Volume Monitoring

Each table has expected daily volume ranges. A deviation of more than 2 standard deviations from the 14-day rolling average triggers a warning. 3 standard deviations triggers a critical alert.

## Schema Change Policy

Schema changes to raw tables must be communicated 48 hours in advance. Breaking changes (column removal, type change) require a migration plan approved by the data engineering team.
