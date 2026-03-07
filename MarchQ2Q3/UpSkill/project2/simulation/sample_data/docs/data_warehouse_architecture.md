# Data Warehouse Architecture

Our data warehouse follows a medallion architecture with three layers:

## Raw Layer
The raw layer ingests data from operational databases via CDC (Change Data Capture). Tables include orders, customers, payments, products, sessions, and inventory. Data arrives with minimal transformation — only schema enforcement and deduplication.

## Staging Layer
Staging models (prefixed `stg_`) apply type casting, column renaming, and basic filtering. Each staging model maps 1:1 to a raw source table. These are materialized as views for cost efficiency.

## Marts Layer
Mart models combine multiple staging or intermediate models into business-ready fact and dimension tables. The orders_mart, customers_mart, and products_mart are the primary consumption models.

## Intermediate Models
Intermediate models (prefixed `int_`) handle complex joins that are reused across multiple marts. For example, int_order_payments joins orders with their aggregated payment data.
