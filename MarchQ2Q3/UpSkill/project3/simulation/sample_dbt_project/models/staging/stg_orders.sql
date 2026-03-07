with source as (
    select * from {{ source('raw', 'orders') }}
),

renamed as (
    select
        id as order_id,
        customer_id,
        order_date,
        status,
        amount,
        tax_rate,
        discount_amount,
        created_at,
        updated_at
    from source
)

select * from renamed
