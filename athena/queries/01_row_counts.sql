-- Confirm row counts across all three Delta tables after a pipeline run.
-- Run in the Athena console or via the AWS CLI using the lakehouse workgroup.

SELECT 'products'    AS dataset, COUNT(*) AS row_count FROM lakehouse.products
UNION ALL
SELECT 'orders'      AS dataset, COUNT(*) AS row_count FROM lakehouse.orders
UNION ALL
SELECT 'order_items' AS dataset, COUNT(*) AS row_count FROM lakehouse.order_items
ORDER BY dataset;
