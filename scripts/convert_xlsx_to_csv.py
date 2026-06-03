"""
Pre-flight converter: transforms .xlsx source files into UTF-8 CSVs ready
for upload to the S3 raw zone. Run once locally before any deployment.

Usage:
    pip install openpyxl
    python scripts/convert_xlsx_to_csv.py [--data-dir Data] [--out-dir data_csv]
"""

import argparse
import sys
from pathlib import Path

try:
    import openpyxl  # noqa: F401 — presence check before pandas import
    import pandas as pd
except ImportError:
    sys.exit("Install dependencies first: pip install pandas openpyxl")


XLSX_MAP = {
    "orders_apr_2025.xlsx": "orders_apr_2025.csv",
    "order_items_apr_2025.xlsx": "order_items_apr_2025.csv",
}


def convert(data_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Copy the CSV that is already in the right format
    products_src = data_dir / "products.csv"
    if products_src.exists():
        import shutil
        dest = out_dir / "products.csv"
        shutil.copy2(products_src, dest)
        print(f"Copied  {products_src.name} → {dest}")
    else:
        print(f"WARNING: {products_src} not found — skipping", file=sys.stderr)

    for xlsx_name, csv_name in XLSX_MAP.items():
        src = data_dir / xlsx_name
        if not src.exists():
            print(f"WARNING: {src} not found — skipping", file=sys.stderr)
            continue

        df = pd.read_excel(src, engine="openpyxl")
        dest = out_dir / csv_name
        df.to_csv(dest, index=False, encoding="utf-8")
        print(f"Converted {xlsx_name} → {csv_name}  ({len(df):,} rows)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert xlsx source files to CSV for S3 ingestion")
    parser.add_argument("--data-dir", default="Data", help="Directory containing source files")
    parser.add_argument("--out-dir", default="data_csv", help="Output directory for CSVs")
    args = parser.parse_args()

    convert(Path(args.data_dir), Path(args.out_dir))
    print("Done. Upload data_csv/ contents to s3://<bucket>/raw/<dataset>/")


if __name__ == "__main__":
    main()
