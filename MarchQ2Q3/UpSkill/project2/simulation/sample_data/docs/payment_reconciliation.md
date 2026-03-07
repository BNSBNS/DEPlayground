# Payment Reconciliation Process

## Overview

The payment_reconciliation model runs daily at 07:00 UTC and compares order totals against payment processor records. It produces a daily reconciliation report stored in the finance schema.

## Metrics

- **Expected Revenue**: Sum of order_total for delivered orders on the given date.
- **Collected Revenue**: Sum of successful payment amounts from the payment processor.
- **Discrepancy**: Difference between expected and collected. Positive values indicate under-collection.
- **Unmatched Orders**: Orders without a corresponding payment record within 48 hours.

## Escalation

If discrepancy exceeds 1% of expected revenue or unmatched_orders exceeds 5, the finance_reconciliation dashboard triggers an alert to the finance-team Slack channel.
