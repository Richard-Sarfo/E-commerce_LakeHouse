"""
Upload converted CSVs to the S3 raw zone for a demo or test run.

Usage:
    python scripts/upload_raw.py --bucket <bucket-name> [--data-dir data_csv]

Requires AWS credentials configured (aws configure / IAM role / env vars).
"""

import argparse
import sys
from pathlib import Path

try:
    import boto3
except ImportError:
    sys.exit("Install boto3 first: pip install boto3")

DATASET_MAP = {
    "products.csv": "products",
    "orders_apr_2025.csv": "orders",
    "order_items_apr_2025.csv": "order_items",
}


def upload(bucket: str, data_dir: Path) -> None:
    s3 = boto3.client("s3")
    for filename, dataset in DATASET_MAP.items():
        local = data_dir / filename
        if not local.exists():
            print(f"WARNING: {local} not found — skipping", file=sys.stderr)
            continue
        key = f"raw/{dataset}/{filename}"
        s3.upload_file(str(local), bucket, key)
        print(f"Uploaded {local} → s3://{bucket}/{key}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload raw CSVs to S3 raw zone")
    parser.add_argument("--bucket", required=True, help="Target S3 bucket name")
    parser.add_argument("--data-dir", default="data_csv", help="Source directory of converted CSVs")
    args = parser.parse_args()

    upload(args.bucket, Path(args.data_dir))
    print("Upload complete. EventBridge will trigger the Step Functions pipeline.")


if __name__ == "__main__":
    main()
