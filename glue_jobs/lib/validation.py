"""
Row-level validation and deduplication for all datasets.

Each function returns (good_df, rejected_df) — rejected rows carry a
_reject_reason string so they can be audited from the rejected/ S3 prefix.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

if TYPE_CHECKING:
    pass


def _tag_reject(df: DataFrame, condition: Column, reason: str) -> tuple[DataFrame, DataFrame]:
    """Split df into (good, bad) where bad rows match condition and get reason tag."""
    from pyspark.sql import functions as F  # local import keeps module importable without Spark

    bad = df.filter(condition).withColumn("_reject_reason", F.lit(reason))
    good = df.filter(~condition)
    return good, bad


def validate_nulls(df: DataFrame, pk_cols: list[str]) -> tuple[DataFrame, list[DataFrame]]:
    """Reject rows where any primary-key column is null."""
    rejects = []
    for col in pk_cols:
        good, bad = _tag_reject(df, F.col(col).isNull(), f"null_pk:{col}")
        rejects.append(bad)
        df = good
    return df, rejects


def validate_timestamps(df: DataFrame, ts_col: str | None) -> tuple[DataFrame, list[DataFrame]]:
    """Reject rows where the timestamp column cannot be parsed."""
    if ts_col is None:
        return df, []

    parsed = df.withColumn("_ts_parsed", F.to_timestamp(F.col(ts_col)))
    good = parsed.filter(F.col("_ts_parsed").isNotNull()).drop("_ts_parsed")
    bad = (
        parsed.filter(F.col("_ts_parsed").isNull())
        .drop("_ts_parsed")
        .withColumn("_reject_reason", F.lit(f"bad_timestamp:{ts_col}"))
    )
    return good, [bad]


def validate_non_negative(df: DataFrame, cols: list[str]) -> tuple[DataFrame, list[DataFrame]]:
    """Reject rows with negative values in financial / quantity columns."""
    rejects = []
    for col in cols:
        good, bad = _tag_reject(
            df,
            F.col(col).isNotNull() & (F.col(col) < 0),
            f"negative_value:{col}",
        )
        rejects.append(bad)
        df = good
    return df, rejects


def validate_referential_integrity(
    df: DataFrame,
    ri_rules: list[tuple[str, str, str]],
    processed_root: str,
    spark: SparkSession,
) -> tuple[DataFrame, list[DataFrame]]:
    """
    Anti-join against already-loaded Delta reference tables.

    ri_rules: list of (local_col, ref_dataset, ref_col)
    processed_root: s3://<bucket>/processed
    """
    rejects = []
    for local_col, ref_dataset, ref_col in ri_rules:
        ref_path = f"{processed_root}/{ref_dataset}"
        try:
            ref_df = spark.read.format("delta").load(ref_path).select(
                F.col(ref_col).alias("__ref")
            )
        except Exception:
            # Reference table not yet populated on a first-ever run — skip RI
            continue

        joined = df.join(ref_df, df[local_col] == F.col("__ref"), "left_outer")
        bad = (
            joined.filter(F.col("__ref").isNull())
            .drop("__ref")
            .withColumn("_reject_reason", F.lit(f"ri_miss:{local_col}→{ref_dataset}.{ref_col}"))
        )
        good = joined.filter(F.col("__ref").isNotNull()).drop("__ref")
        rejects.append(bad)
        df = good
    return df, rejects


def deduplicate(df: DataFrame, pk_cols: list[str], ts_col: str | None) -> DataFrame:
    """
    Keep one row per primary key.

    Strategy:
    - If a timestamp column exists: keep the row with the latest timestamp.
    - Otherwise (products): keep the last row in file order (monotonically_increasing_id).
    """
    if ts_col is not None:
        order_expr = F.col(ts_col).desc()
    else:
        order_expr = F.monotonically_increasing_id().desc()

    window = Window.partitionBy(*pk_cols).orderBy(order_expr)
    return (
        df.withColumn("_row_num", F.row_number().over(window))
        .filter(F.col("_row_num") == 1)
        .drop("_row_num")
    )


def run_all_validations(
    df: DataFrame,
    dataset: str,
    processed_root: str,
    spark: SparkSession,
    config: dict,
) -> tuple[DataFrame, DataFrame]:
    """
    Run the full validation suite for a dataset.

    Returns (good_df, rejected_df).  rejected_df includes _reject_reason.
    """
    all_rejects: list[DataFrame] = []

    df, r = validate_nulls(df, config["pk"])
    all_rejects.extend(r)

    df, r = validate_timestamps(df, config["timestamp_col"])
    all_rejects.extend(r)

    df, r = validate_non_negative(df, config["non_negative"])
    all_rejects.extend(r)

    df, r = validate_referential_integrity(df, config["ri"], processed_root, spark)
    all_rejects.extend(r)

    df = deduplicate(df, config["pk"], config["timestamp_col"])

    non_empty = [r for r in all_rejects if r is not None]
    if non_empty:
        schema_with_reason = df.schema
        # Align schemas: add _reject_reason to good_df schema cols for union
        reject_union = non_empty[0]
        for r in non_empty[1:]:
            reject_union = reject_union.unionByName(r, allowMissingColumns=True)
    else:
        reject_union = spark.createDataFrame([], df.schema)

    return df, reject_union
