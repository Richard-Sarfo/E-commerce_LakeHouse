"""Unit tests for glue_jobs/lib/validation.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "glue_jobs"))

from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, StringType, StructField, StructType

from lib.validation import (
    deduplicate,
    validate_non_negative,
    validate_nulls,
    validate_timestamps,
)


@pytest.fixture()
def orders_schema():
    return StructType([
        StructField("order_id",        IntegerType(), True),
        StructField("user_id",         IntegerType(), True),
        StructField("order_timestamp", StringType(),  True),
        StructField("total_amount",    IntegerType(), True),
    ])


class TestValidateNulls:
    def test_rejects_null_pk(self, spark, orders_schema):
        df = spark.createDataFrame(
            [(1, 10, "2025-04-01 10:00:00", 50), (None, 20, "2025-04-01 11:00:00", 60)],
            orders_schema,
        )
        good, rejects = validate_nulls(df, ["order_id"])
        assert good.count() == 1
        assert rejects[0].count() == 1
        assert rejects[0].first()["_reject_reason"] == "null_pk:order_id"

    def test_passes_non_null_pk(self, spark, orders_schema):
        df = spark.createDataFrame(
            [(1, 10, "2025-04-01 10:00:00", 50), (2, 20, "2025-04-01 11:00:00", 60)],
            orders_schema,
        )
        good, rejects = validate_nulls(df, ["order_id"])
        assert good.count() == 2
        assert rejects[0].count() == 0


class TestValidateTimestamps:
    def test_rejects_unparseable_timestamp(self, spark, orders_schema):
        df = spark.createDataFrame(
            [(1, 10, "not-a-date", 50), (2, 20, "2025-04-01 11:00:00", 60)],
            orders_schema,
        )
        good, rejects = validate_timestamps(df, "order_timestamp")
        assert good.count() == 1
        assert rejects[0].count() == 1
        assert "bad_timestamp" in rejects[0].first()["_reject_reason"]

    def test_skips_when_no_ts_col(self, spark, orders_schema):
        df = spark.createDataFrame([(1, 10, "anything", 50)], orders_schema)
        good, rejects = validate_timestamps(df, None)
        assert good.count() == 1
        assert rejects == []


class TestValidateNonNegative:
    def test_rejects_negative_amount(self, spark, orders_schema):
        df = spark.createDataFrame(
            [(1, 10, "2025-04-01", 50), (2, 20, "2025-04-01", -5)],
            orders_schema,
        )
        good, rejects = validate_non_negative(df, ["total_amount"])
        assert good.count() == 1
        assert rejects[0].count() == 1
        assert "negative_value" in rejects[0].first()["_reject_reason"]


class TestDeduplicate:
    def test_keeps_latest_by_timestamp(self, spark):
        schema = StructType([
            StructField("order_id",        IntegerType(), True),
            StructField("order_timestamp", StringType(),  True),
            StructField("total_amount",    IntegerType(), True),
        ])
        df = spark.createDataFrame(
            [(1, "2025-04-01 08:00:00", 50), (1, "2025-04-01 12:00:00", 99)],
            schema,
        )
        result = deduplicate(df, ["order_id"], "order_timestamp")
        assert result.count() == 1
        assert result.first()["total_amount"] == 99

    def test_no_duplicates_unchanged(self, spark):
        schema = StructType([
            StructField("order_id",        IntegerType(), True),
            StructField("order_timestamp", StringType(),  True),
            StructField("total_amount",    IntegerType(), True),
        ])
        df = spark.createDataFrame(
            [(1, "2025-04-01 08:00:00", 50), (2, "2025-04-01 12:00:00", 99)],
            schema,
        )
        result = deduplicate(df, ["order_id"], "order_timestamp")
        assert result.count() == 2
