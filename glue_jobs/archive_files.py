"""
Python-shell Glue job that archives successfully processed raw files.

Copies each raw CSV to archived/<dataset>/YYYY-MM-DD/<filename> then
deletes the original, keeping the raw/ prefix clean.

Glue job arguments:
    --bucket          S3 bucket name (no s3:// prefix)
    --raw_keys        Comma-separated list of raw/ object keys to archive
    --archive_date    YYYY-MM-DD date string (injected from Step Functions)
"""

import logging
import sys
from datetime import datetime

import boto3
from awsglue.utils import getResolvedOptions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def archive_key(s3_client, bucket: str, raw_key: str, archive_date: str) -> None:
    """Copy raw_key → archived/<dataset>/<date>/<filename>, then delete original."""
    # raw/orders/orders_apr_2025.csv  →  archived/orders/2025-04-30/orders_apr_2025.csv
    parts = raw_key.split("/")            # ['raw', 'orders', 'orders_apr_2025.csv']
    dataset = parts[1] if len(parts) >= 3 else "unknown"
    filename = parts[-1]
    dest_key = f"archived/{dataset}/{archive_date}/{filename}"

    s3_client.copy_object(
        Bucket=bucket,
        CopySource={"Bucket": bucket, "Key": raw_key},
        Key=dest_key,
    )
    logger.info("Copied s3://%s/%s → s3://%s/%s", bucket, raw_key, bucket, dest_key)

    s3_client.delete_object(Bucket=bucket, Key=raw_key)
    logger.info("Deleted s3://%s/%s", bucket, raw_key)


def main() -> None:
    args = getResolvedOptions(sys.argv, ["bucket", "raw_keys", "archive_date"])

    bucket = args["bucket"]
    archive_date = args["archive_date"]
    raw_keys = [k.strip() for k in args["raw_keys"].split(",") if k.strip()]

    s3 = boto3.client("s3")

    for key in raw_keys:
        try:
            archive_key(s3, bucket, key, archive_date)
        except Exception as exc:
            logger.error("Failed to archive %s: %s", key, exc)
            raise  # surface to Step Functions for Catch handling

    logger.info("Archived %d file(s) dated %s", len(raw_keys), archive_date)


if __name__ == "__main__":
    main()
