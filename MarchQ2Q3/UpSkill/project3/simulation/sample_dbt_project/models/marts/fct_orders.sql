with orders as (
    select * from {{ ref('stg_orders') }}
),

payments as (
    select
        order_id,
        sum(amount) as total_paid
    from {{ ref('stg_payments') }}
    where status = 'completed'
    group by order_id
),

final as (
    select
        o.order_id,
        o.customer_id,
        o.order_date,
        o.status,
        o.amount as order_amount,
        o.tax_rate,
        o.discount_amount,
        coalesce(p.total_paid, 0) as total_paid,
        o.amount - coalesce(p.total_paid, 0) as amount_due,
        o.created_at,
        o.updated_at
    from orders o
    left join payments p on o.order_id = p.order_id
)

select * from final
