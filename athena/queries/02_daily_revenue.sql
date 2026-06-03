-- Daily revenue trend from the orders table.
-- Partition pruning fires on the `date` column, keeping scan cost low.

SELECT
    date,
    COUNT(DISTINCT order_id)    AS orders_placed,
    SUM(total_amount)           AS gross_revenue,
    AVG(total_amount)           AS avg_order_value
FROM lakehouse.orders
WHERE date BETWEEN '2025-04-01' AND '2025-04-30'
GROUP BY date
ORDER BY date;
