with customers as (
    select * from {{ ref('stg_customers') }}
),

orders as (
    select
        customer_id,
        count(*) as order_count,
        sum(order_amount) as total_spent,
        min(order_date) as first_order_date,
        max(order_date) as last_order_date
    from {{ ref('fct_orders') }}
    group by customer_id
),

final as (
    select
        c.customer_id,
        c.first_name,
        c.last_name,
        c.email,
        coalesce(o.order_count, 0) as order_count,
        coalesce(o.total_spent, 0) as total_spent,
        o.first_order_date,
        o.last_order_date,
        c.created_at,
        c.updated_at
    from customers c
    left join orders o on c.customer_id = o.customer_id
)

select * from final
