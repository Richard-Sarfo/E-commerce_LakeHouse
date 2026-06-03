-- Reorder rate per product — what fraction of order-item rows are re-orders.
-- Useful for product affinity and inventory planning.

SELECT
    p.product_name,
    p.department,
    COUNT(oi.id)                                        AS total_line_items,
    SUM(oi.reordered)                                   AS reordered_count,
    ROUND(100.0 * SUM(oi.reordered) / COUNT(oi.id), 2) AS reorder_rate_pct
FROM lakehouse.order_items oi
JOIN lakehouse.products p
    ON oi.product_id = p.product_id
GROUP BY p.product_name, p.department
HAVING COUNT(oi.id) >= 10
ORDER BY reorder_rate_pct DESC
LIMIT 20;
