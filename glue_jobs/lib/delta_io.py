"""
Delta Lake read/write helpers.

Wraps the merge (upsert) pattern so each dataset's ETL job calls a single
function rather than repeating the DeltaTable API boilerplate.
"""

from __future__ import annotations

import logging

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

logger = logging.getLogger(__name__)


def write_delta_merge(
    spark: SparkSession,
    new_df: DataFrame,
    target_path: str,
    pk_cols: list[str],
    partition_cols: list[str],
) -> dict[str, int]:
    """
    Upsert new_df into the Delta table at target_path.

    - First write (table absent): creates the table with correct partitioning.
    - Subsequent writes: MERGE matched rows (update all) + insert new rows.

    Returns a dict of row counts for CloudWatch metrics.
    """
    from delta.tables import DeltaTable  # imported here so unit tests can mock

    rows_in = new_df.count()

    join_condition = " AND ".join(
        f"target.{c} = source.{c}" for c in pk_cols
    )

    if DeltaTable.isDeltaTable(spark, target_path):
        delta_tbl = DeltaTable.forPath(spark, target_path)
        (
            delta_tbl.alias("target")
            .merge(new_df.alias("source"), join_condition)
            .whenMatchedUpdateAll()
            .whenNotMatchedInsertAll()
            .execute()
        )
        rows_merged = rows_in  # approximation; Delta doesn't expose per-merge counts easily
        logger.info("MERGE into %s: %d rows processed", target_path, rows_merged)
    else:
        writer = new_df.write.format("delta").mode("overwrite")
        if partition_cols:
            writer = writer.partitionBy(*partition_cols)
        writer.save(target_path)
        rows_merged = rows_in
        logger.info("Initial write to %s: %d rows", target_path, rows_merged)

    return {"rows_in": rows_in, "rows_merged": rows_merged}


def write_rejected(rejected_df: DataFrame, rejected_path: str) -> int:
    """Write rejected rows to Parquet in the rejected/ prefix."""
    if rejected_df.rdd.isEmpty():
        return 0
    count = rejected_df.count()
    rejected_df.write.mode("overwrite").parquet(rejected_path)
    logger.info("Wrote %d rejected rows to %s", count, rejected_path)
    return count


def emit_cloudwatch_metrics(
    dataset: str,
    rows_in: int,
    rows_rejected: int,
    rows_merged: int,
    namespace: str = "Lakehouse/ETL",
) -> None:
    """Push custom metrics to CloudWatch (best-effort; failure does not abort the job)."""
    try:
        import boto3

        cw = boto3.client("cloudwatch")
        cw.put_metric_data(
            Namespace=namespace,
            MetricData=[
                {"MetricName": "RowsIn",       "Dimensions": [{"Name": "Dataset", "Value": dataset}], "Value": rows_in,       "Unit": "Count"},
                {"MetricName": "RowsRejected", "Dimensions": [{"Name": "Dataset", "Value": dataset}], "Value": rows_rejected, "Unit": "Count"},
                {"MetricName": "RowsMerged",   "Dimensions": [{"Name": "Dataset", "Value": dataset}], "Value": rows_merged,   "Unit": "Count"},
            ],
        )
    except Exception as exc:
        logger.warning("CloudWatch metric push failed (non-fatal): %s", exc)
