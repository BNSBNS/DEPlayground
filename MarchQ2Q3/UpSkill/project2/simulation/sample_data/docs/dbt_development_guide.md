# dbt Development Guide

## Naming Conventions

- **Sources**: Raw table names (e.g., `orders`, `customers`)
- **Staging**: `stg_{source_name}` (e.g., `stg_orders`)
- **Intermediate**: `int_{description}` (e.g., `int_order_payments`)
- **Marts**: `{domain}_mart` or descriptive name (e.g., `orders_mart`, `revenue_daily`)

## Materialization Strategy

| Layer | Materialization | Reason |
|-------|----------------|--------|
| Staging | View | Low cost, always fresh |
| Intermediate | Ephemeral | No storage cost, inlined into downstream |
| Marts | Table | Fast query performance |
| Metrics | Table or Incremental | Balance freshness and cost |

## Testing

Every model must have:
1. A unique test on its primary key
2. Not-null tests on required columns
3. Accepted-values tests on status/enum columns
4. Relationship tests for foreign keys

## Running Locally

```bash
dbt run --select staging      # Run all staging models
dbt run --select +orders_mart  # Run orders_mart and all upstream
dbt test --select orders_mart  # Test orders_mart
```
