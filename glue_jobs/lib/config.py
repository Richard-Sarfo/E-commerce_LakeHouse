"""
Central registry for per-dataset schema, primary keys, partitioning,
and referential integrity constraints.

Adding a new dataset means adding one entry here; no other module changes.
"""

from pyspark.sql.types import (
    DecimalType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# ---------------------------------------------------------------------------
# Schemas — explicit, no inferSchema, satisfies the "schema enforcement" req.
# ---------------------------------------------------------------------------

SCHEMAS: dict[str, StructType] = {
    "products": StructType([
        StructField("product_id",   IntegerType(), nullable=False),
        StructField("department_id", IntegerType(), nullable=False),
        StructField("department",   StringType(),  nullable=True),
        StructField("product_name", StringType(),  nullable=True),
    ]),
    "orders": StructType([
        StructField("order_num",        LongType(),    nullable=True),
        StructField("order_id",         IntegerType(), nullable=False),
        StructField("user_id",          IntegerType(), nullable=True),
        StructField("order_timestamp",  StringType(),  nullable=True),  # parsed later
        StructField("total_amount",     DecimalType(12, 2), nullable=True),
        StructField("date",             StringType(),  nullable=True),
    ]),
    "order_items": StructType([
        StructField("id",                    LongType(),    nullable=False),
        StructField("order_id",              IntegerType(), nullable=False),
        StructField("user_id",               IntegerType(), nullable=True),
        StructField("days_since_prior_order", IntegerType(), nullable=True),
        StructField("product_id",            IntegerType(), nullable=False),
        StructField("add_to_cart_order",     IntegerType(), nullable=True),
        StructField("reordered",             IntegerType(), nullable=True),
        StructField("order_timestamp",       StringType(),  nullable=True),
        StructField("date",                  StringType(),  nullable=True),
    ]),
}

# ---------------------------------------------------------------------------
# Per-dataset behaviour
# ---------------------------------------------------------------------------

DATASETS: dict[str, dict] = {
    "products": {
        "pk":            ["product_id"],
        "timestamp_col": None,          # no timestamp; dedup by last-in-file
        "partition":     [],
        "ri": [],                       # no foreign keys
        "non_negative":  [],
    },
    "orders": {
        "pk":            ["order_id"],
        "timestamp_col": "order_timestamp",
        "partition":     ["date"],
        "ri": [],
        "non_negative":  ["total_amount"],
    },
    "order_items": {
        "pk":            ["id"],
        "timestamp_col": "order_timestamp",
        "partition":     ["date"],
        # (local_col, ref_dataset, ref_col) — checked after products+orders are loaded
        "ri": [
            ("order_id",   "orders",   "order_id"),
            ("product_id", "products", "product_id"),
        ],
        "non_negative":  [],
    },
}
