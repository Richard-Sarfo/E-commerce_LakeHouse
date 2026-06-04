"""
Row-level validation and deduplication for all lakehouse datasets.

Every public function returns ``(good_df, rejected_df_list)`` so the caller
can union the rejects and write them to ``rejected/<dataset>/run=<id>/``
for audit. Rejected rows carry a ``_reject_reason`` string column.

The validation suite enforces:

- Non-null primary keys
- Parseable timestamps
- Non-negative values on financial / quantity columns
- Referential integrity against already-loaded Delta reference tables
- Deduplication by latest timestamp (or last-in-file when no timestamp exists)
"""

from __future__ import annotations

from pyspark.sql import Column, DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def _tag_reject(
    df: DataFrame,
    condition: Column,
    reason: str,
) -> tuple[DataFrame, DataFrame]:
    """Split ``df`` into ``(good, bad)`` by ``condition``.

    Rows matching ``condition`` are tagged with ``_reject_reason=reason``
    and returned as the second element. Surviving rows are the first.
    """
    bad = df.filter(condition).withColumn("_reject_reason", F.lit(reason))
    good = df.filter(~condition)
    return good, bad


def validate_nulls(
    df: DataFrame,
    pk_cols: list[str],
) -> tuple[DataFrame, list[DataFrame]]:
    """Reject rows where any primary-key column is null.

    Iterates ``pk_cols`` in order so a row missing two PK columns is only
    rejected once (against the first missing column).
    """
    rejects: list[DataFrame] = []
    for col in pk_cols:
        good, bad = _tag_reject(df, F.col(col).isNull(), f"null_pk:{col}")
        rejects.append(bad)
        df = good
    return df, rejects


def validate_timestamps(
    df: DataFrame,
    ts_col: str | None,
) -> tuple[DataFrame, list[DataFrame]]:
    """Reject rows where ``ts_col`` cannot be parsed as a timestamp.

    Returns ``(df, [])`` unchanged when ``ts_col`` is ``None`` (e.g. the
    products dimension has no timestamp).
    """
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


def validate_non_negative(
    df: DataFrame,
    cols: list[str],
) -> tuple[DataFrame, list[DataFrame]]:
    """Reject rows where any of ``cols`` is non-null and < 0.

    Null values pass — only explicit negatives are rejected.
    """
    rejects: list[DataFrame] = []
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
    """Anti-join against already-loaded Delta reference tables.

    Each rule is ``(local_col, ref_dataset, ref_col)``. If the referenced
    Delta table does not yet exist (first-ever run), the check is skipped
    rather than failing — initial bootstrap deserves to succeed.
    """
    rejects: list[DataFrame] = []
    for local_col, ref_dataset, ref_col in ri_rules:
        ref_path = f"{processed_root}/{ref_dataset}"
        try:
            ref_df = spark.read.format("delta").load(ref_path).select(
                F.col(ref_col).alias("__ref")
            )
        except Exception:
            # Reference table absent on first-ever run — skip RI for this rule.
            continue

        joined = df.join(ref_df, df[local_col] == F.col("__ref"), "left_outer")
        bad = (
            joined.filter(F.col("__ref").isNull())
            .drop("__ref")
            .withColumn(
                "_reject_reason",
                F.lit(f"ri_miss:{local_col}->{ref_dataset}.{ref_col}"),
            )
        )
        good = joined.filter(F.col("__ref").isNotNull()).drop("__ref")
        rejects.append(bad)
        df = good
    return df, rejects


def deduplicate(
    df: DataFrame,
    pk_cols: list[str],
    ts_col: str | None,
) -> DataFrame:
    """Keep one row per primary key.

    With a timestamp column: keep the latest by timestamp. Without:
    keep the last row in file order (via ``monotonically_increasing_id``)
    — sufficient for the products dimension where the file is the source
    of truth.
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
    """Run the full validation suite for a dataset.

    Order matters: null checks before timestamp parsing (a null PK should
    not become a "bad timestamp" reject), non-negative before RI (cheap
    filters first), dedup last. Returns the final ``(good_df, rejected_df)``
    with all rejects unioned into a single DataFrame carrying the
    ``_reject_reason`` column.
    """
    all_rejects: list[DataFrame] = []

    df, r = validate_nulls(df, config["pk"])
    all_rejects.extend(r)

    df, r = validate_timestamps(df, config["timestamp_col"])
    all_rejects.extend(r)

    df, r = validate_non_negative(df, config["non_negative"])
    all_rejects.extend(r)

    df, r = validate_referential_integrity(
        df, config["ri"], processed_root, spark,
    )
    all_rejects.extend(r)

    df = deduplicate(df, config["pk"], config["timestamp_col"])

    non_empty = [r for r in all_rejects if r is not None]
    if non_empty:
        reject_union = non_empty[0]
        for r in non_empty[1:]:
            reject_union = reject_union.unionByName(r, allowMissingColumns=True)
    else:
        reject_union = spark.createDataFrame([], df.schema)

    return df, reject_union
