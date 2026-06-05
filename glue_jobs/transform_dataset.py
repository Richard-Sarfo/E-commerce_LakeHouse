"""
Parametrized Glue ETL job — one script handles all three datasets.

Glue job arguments (passed via Step Functions / --default_arguments):
    --dataset          products | orders | order_items
    --input_s3         s3://<bucket>/raw/<dataset>/<file>.csv
    --processed_root   s3://<bucket>/processed
    --rejected_root    s3://<bucket>/rejected
    --run_id           $$.Execution.Name  (injected by Step Functions)

The job:
  1. Reads the CSV with an explicit schema (schema enforcement)
  2. Runs all validations, writing rejects to rejected_root
  3. Deduplicates by primary key
  4. Merges into the target Delta table (upsert)
  5. Emits row-count metrics to CloudWatch
"""

import logging
import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from lib.config import DATASETS, SCHEMAS
from lib.delta_io import emit_cloudwatch_metrics, write_delta_merge, write_rejected
from lib.validation import run_all_validations
from pyspark.context import SparkContext

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args() -> dict:
    required = ["JOB_NAME", "dataset", "input_s3", "processed_root", "rejected_root", "run_id"]
    return getResolvedOptions(sys.argv, required)


def main() -> None:
    args = parse_args()
    dataset = args["dataset"]

    if dataset not in DATASETS:
        raise ValueError(f"Unknown dataset '{dataset}'. Valid: {list(DATASETS)}")

    sc = SparkContext()
    glue_ctx = GlueContext(sc)
    spark = glue_ctx.spark_session
    job = Job(glue_ctx)
    job.init(args["JOB_NAME"], args)

    config = DATASETS[dataset]
    schema = SCHEMAS[dataset]

    logger.info("Starting ETL for dataset=%s run_id=%s", dataset, args["run_id"])

    # ------------------------------------------------------------------
    # 1. Read CSV with explicit schema — no inferSchema
    # ------------------------------------------------------------------
    raw_df = (
        spark.read
        .format("csv")
        .option("header", "true")
        .option("nullValue", "")
        .schema(schema)
        .load(args["input_s3"])
    )
    rows_in = raw_df.count()
    logger.info("Read %d rows from %s", rows_in, args["input_s3"])

    # ------------------------------------------------------------------
    # 2. Validate + deduplicate
    # ------------------------------------------------------------------
    good_df, rejected_df = run_all_validations(
        raw_df,
        dataset=dataset,
        processed_root=args["processed_root"],
        spark=spark,
        config=config,
    )

    # ------------------------------------------------------------------
    # 3. Write rejected rows
    # ------------------------------------------------------------------
    rejected_path = f"{args['rejected_root']}/{dataset}/run={args['run_id']}"
    rows_rejected = write_rejected(rejected_df, rejected_path)

    # ------------------------------------------------------------------
    # 4. Merge into Delta table
    # ------------------------------------------------------------------
    target_path = f"{args['processed_root']}/{dataset}"
    metrics = write_delta_merge(
        spark,
        good_df,
        target_path,
        config["pk"],
        config["partition"],
    )

    # ------------------------------------------------------------------
    # 5. CloudWatch metrics
    # ------------------------------------------------------------------
    emit_cloudwatch_metrics(
        dataset=dataset,
        rows_in=rows_in,
        rows_rejected=rows_rejected,
        rows_merged=metrics["rows_merged"],
    )

    logger.info(
        "ETL complete: dataset=%s rows_in=%d rows_rejected=%d rows_merged=%d",
        dataset,
        rows_in,
        rows_rejected,
        metrics["rows_merged"],
    )

    job.commit()


if __name__ == "__main__":
    main()
