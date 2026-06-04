-- Department-pair co-occurrence: which department combinations show up
-- together in the same cart, ranked by frequency.
--
-- Useful for cross-merchandising decisions. Self-joins order_items via
-- a < b to avoid duplicate (A,B)/(B,A) pairs and reflexive (A,A) pairs.

WITH order_departments AS (
    SELECT DISTINCT
        oi.order_id,
        p.department
    FROM lakehouse.order_items oi
    JOIN lakehouse.products p
        ON oi.product_id = p.product_id
)
SELECT
    a.department AS dept_a,
    b.department AS dept_b,
    COUNT(*)     AS orders_with_both
FROM order_departments a
JOIN order_departments b
    ON a.order_id   = b.order_id
   AND a.department < b.department
GROUP BY a.department, b.department
ORDER BY orders_with_both DESC
LIMIT 20;
