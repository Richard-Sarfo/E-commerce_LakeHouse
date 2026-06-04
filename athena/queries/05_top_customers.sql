-- Top 20 customers by lifetime gross revenue across the period.
-- Joins orders → order_items only when both partitions are loaded so partition
-- pruning still applies even on this multi-table aggregate.

SELECT
    o.user_id,
    COUNT(DISTINCT o.order_id)              AS orders_placed,
    SUM(oi.add_to_cart_order)               AS items_per_cart_total,
    SUM(o.total_amount)                     AS lifetime_revenue,
    ROUND(AVG(o.total_amount), 2)           AS avg_order_value,
    MAX(CAST(o.order_timestamp AS varchar)) AS last_order_at
FROM lakehouse.orders o
JOIN lakehouse.order_items oi
    ON oi.order_id = o.order_id
   AND oi.date     = o.date
WHERE o.date BETWEEN '2025-04-01' AND '2025-04-30'
GROUP BY o.user_id
ORDER BY lifetime_revenue DESC
LIMIT 20;
