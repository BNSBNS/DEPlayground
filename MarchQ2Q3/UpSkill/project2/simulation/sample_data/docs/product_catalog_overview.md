# Product Catalog Overview

## Structure

Products are organized into five categories: Electronics, Clothing, Home & Garden, Sports, and Books. Each product has a unique product_id, name, category, base price, and supplier reference.

## Products Mart

The products_mart model enriches the raw product catalog with:
- **total_revenue**: Lifetime revenue from all orders containing this product.
- **units_sold**: Total quantity sold across all orders.
- **current_stock**: Latest inventory level summed across all warehouses.

## Inventory Alerts

The inventory_alerts model calculates days_until_stockout based on a 7-day rolling average of daily sales velocity. Alert levels are:
- **critical**: Less than 3 days of stock remaining
- **warning**: Less than 7 days of stock remaining
- **healthy**: 7 or more days of stock remaining
