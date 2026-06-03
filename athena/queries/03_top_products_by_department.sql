-- Top 10 most-ordered products per department in April 2025.
-- Joins the three Delta tables to demonstrate cross-table analytics.

WITH ranked AS (
    SELECT
        p.department,
        p.product_name,
        COUNT(oi.id)            AS times_ordered,
        COUNT(DISTINCT oi.order_id) AS unique_orders,
        ROW_NUMBER() OVER (
            PARTITION BY p.department
            ORDER BY COUNT(oi.id) DESC
        ) AS dept_rank
    FROM lakehouse.order_items oi
    JOIN lakehouse.products p
        ON oi.product_id = p.product_id
    JOIN lakehouse.orders o
        ON oi.order_id = o.order_id
    WHERE oi.date BETWEEN '2025-04-01' AND '2025-04-30'
    GROUP BY p.department, p.product_name
)
SELECT department, product_name, times_ordered, unique_orders
FROM ranked
WHERE dept_rank <= 10
ORDER BY department, dept_rank;
