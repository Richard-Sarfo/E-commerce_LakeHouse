"""
Delta Lake read/write helpers used by the parametrized Glue ETL job.

Each ETL run calls :func:`write_delta_merge` exactly once per dataset.
The function handles both the first-write (create table) and
subsequent-write (MERGE / upsert) cases without the caller needing to
know which path it's on.
"""

from __future__ import annotations

import logging
from typing import Any

from pyspark.sql import DataFrame, SparkSession

logger = logging.getLogger(__name__)


def write_delta_merge(
    spark: SparkSession,
    new_df: DataFrame,
    target_path: str,
    pk_cols: list[str],
    partition_cols: list[str],
) -> dict[str, int]:
    """Upsert ``new_df`` into the Delta table at ``target_path``.

    First call against a path that doesn't yet have a ``_delta_log/``
    creates the table with the supplied partition layout. Subsequent
    calls execute a MERGE on ``pk_cols`` — matched rows are updated,
    unmatched rows are inserted. Idempotent on PK collisions.

    Returns a dict with ``rows_in`` and ``rows_merged`` for CloudWatch
    metrics. Note that Delta does not expose a per-MERGE row count, so
    ``rows_merged`` is approximated as ``rows_in`` (every input row
    either updates or inserts).
    """
    from delta.tables import DeltaTable  # local import so unit tests can mock

    rows_in = new_df.count()
    join_condition = " AND ".join(f"target.{c} = source.{c}" for c in pk_cols)

    if DeltaTable.isDeltaTable(spark, target_path):
        delta_tbl = DeltaTable.forPath(spark, target_path)
        (
            delta_tbl.alias("target")
            .merge(new_df.alias("source"), join_condition)
            .whenMatchedUpdateAll()
            .whenNotMatchedInsertAll()
            .execute()
        )
        logger.info("MERGE into %s: %d rows processed", target_path, rows_in)
    else:
        writer = new_df.write.format("delta").mode("overwrite")
        if partition_cols:
            writer = writer.partitionBy(*partition_cols)
        writer.save(target_path)
        logger.info("Initial write to %s: %d rows", target_path, rows_in)

    return {"rows_in": rows_in, "rows_merged": rows_in}


def write_rejected(rejected_df: DataFrame, rejected_path: str) -> int:
    """Write rejected rows to Parquet under ``rejected_path``.

    Parquet (not Delta) is used here intentionally — rejects are an
    immutable audit log per run, not a queryable table that needs ACID
    updates. ``rdd.isEmpty()`` short-circuits the write to avoid creating
    empty directories that confuse partition scanners.
    """
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
    """Push per-run row counts to CloudWatch as custom metrics.

    Failure to push is logged but never aborts the job — observability
    must not block the data path. Three metrics are emitted per call,
    each dimensioned by ``Dataset``: ``RowsIn``, ``RowsRejected``,
    ``RowsMerged``.
    """
    try:
        import boto3

        cw = boto3.client("cloudwatch")
        dim: list[dict[str, Any]] = [{"Name": "Dataset", "Value": dataset}]
        cw.put_metric_data(
            Namespace=namespace,
            MetricData=[
                {"MetricName": "RowsIn",       "Dimensions": dim, "Value": rows_in,       "Unit": "Count"},
                {"MetricName": "RowsRejected", "Dimensions": dim, "Value": rows_rejected, "Unit": "Count"},
                {"MetricName": "RowsMerged",   "Dimensions": dim, "Value": rows_merged,   "Unit": "Count"},
            ],
        )
    except Exception as exc:
        logger.warning("CloudWatch metric push failed (non-fatal): %s", exc)
