"""Unit tests for glue_jobs/lib/delta_io.py — write_delta_merge."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "glue_jobs"))

from lib.delta_io import write_delta_merge
from pyspark.sql.types import IntegerType, StringType, StructField, StructType

PRODUCT_SCHEMA = StructType([
    StructField("product_id",    IntegerType(), True),
    StructField("department_id", IntegerType(), True),
    StructField("product_name",  StringType(),  True),
])


class TestWriteDeltaMerge:
    def test_initial_write_creates_delta_table(self, spark, tmp_path):
        df = spark.createDataFrame(
            [(1, 4, "Widget A"), (2, 2, "Widget B")],
            PRODUCT_SCHEMA,
        )
        path = str(tmp_path / "products")
        metrics = write_delta_merge(spark, df, path, ["product_id"], [])
        assert metrics["rows_in"] == 2
        # Verify Delta table was created
        result = spark.read.format("delta").load(path)
        assert result.count() == 2

    def test_merge_updates_existing_row(self, spark, tmp_path):
        path = str(tmp_path / "products")
        initial = spark.createDataFrame(
            [(1, 4, "Widget A"), (2, 2, "Widget B")],
            PRODUCT_SCHEMA,
        )
        write_delta_merge(spark, initial, path, ["product_id"], [])

        updated = spark.createDataFrame(
            [(1, 4, "Widget A — Revised")],
            PRODUCT_SCHEMA,
        )
        write_delta_merge(spark, updated, path, ["product_id"], [])

        result = spark.read.format("delta").load(path)
        assert result.count() == 2  # row 2 still present
        row1 = result.filter("product_id = 1").first()
        assert row1["product_name"] == "Widget A — Revised"

    def test_merge_inserts_new_row(self, spark, tmp_path):
        path = str(tmp_path / "products")
        initial = spark.createDataFrame([(1, 4, "Widget A")], PRODUCT_SCHEMA)
        write_delta_merge(spark, initial, path, ["product_id"], [])

        new_row = spark.createDataFrame([(3, 6, "Widget C")], PRODUCT_SCHEMA)
        write_delta_merge(spark, new_row, path, ["product_id"], [])

        result = spark.read.format("delta").load(path)
        assert result.count() == 2

    def test_partitioned_write(self, spark, tmp_path):
        schema = StructType([
            StructField("order_id",   IntegerType(), True),
            StructField("date",       StringType(),  True),
            StructField("total",      IntegerType(), True),
        ])
        df = spark.createDataFrame(
            [(101, "2025-04-01", 200), (102, "2025-04-02", 300)],
            schema,
        )
        path = str(tmp_path / "orders")
        write_delta_merge(spark, df, path, ["order_id"], ["date"])
        result = spark.read.format("delta").load(path)
        assert result.count() == 2
