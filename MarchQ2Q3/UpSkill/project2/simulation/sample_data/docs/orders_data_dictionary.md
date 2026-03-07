# Orders Data Dictionary

## orders_mart

The orders_mart table is the primary fact table for order analysis.

| Column | Type | Description |
|--------|------|-------------|
| order_id | UUID | Unique order identifier |
| customer_id | UUID | Reference to customers_mart |
| customer_name | VARCHAR | Denormalized customer name |
| order_total | NUMERIC(18,2) | Total order amount in USD |
| payment_total | NUMERIC(18,2) | Total payments received |
| order_date | DATE | Date the order was placed |
| status | VARCHAR | Current order status (pending, confirmed, shipped, delivered, cancelled) |

## Order Statuses

- **pending**: Order created but not yet confirmed
- **confirmed**: Payment received, awaiting fulfillment
- **shipped**: Order dispatched to carrier
- **delivered**: Order received by customer
- **cancelled**: Order cancelled (refund initiated if payment was made)

## Known Issues

- Orders placed before 2024-01-15 may have NULL payment_total due to a migration issue. Use COALESCE(payment_total, order_total) for historical analysis.
