# Deployment Runbook

Step-by-step instructions for taking the lakehouse from a fresh AWS account to a working end-to-end pipeline. Captures every gotcha discovered during the first live apply.

---

## Prerequisites

| Tool | Why |
|---|---|
| Docker Desktop | Runs Terraform, AWS CLI, and pytest in pinned containers — no host installs needed |
| Python ≥ 3.9 with `pandas` + `openpyxl` | Local xlsx → CSV conversion (only step that needs a host Python) |
| Git Bash / WSL | Path translation works correctly when mounting volumes (PowerShell mangles arg quoting on some Terraform commands) |
| An AWS account with **non-root** IAM user keys | Root keys are explicitly rejected; create an IAM user (`AdministratorAccess` is fine for first deploy) |

## 1. Configure credentials

Copy the template and fill in IAM user keys:

```bash
cp .env.example .env
# Edit .env — replace placeholders with real values
```

Verify:

```bash
docker run --rm --env-file .env amazon/aws-cli:latest sts get-caller-identity
# Expect: "Arn": "arn:aws:iam::<account>:user/<your-iam-user>"  (NOT :root)
```

## 2. Convert source files

```bash
make convert
# or: python scripts/convert_xlsx_to_csv.py
```

Produces `data_csv/products.csv`, `data_csv/orders_apr_2025.csv`, `data_csv/order_items_apr_2025.csv`.

## 3. Provision infrastructure

```bash
make tf-init
make tf-plan        # review the 34 resources
make tf-apply
```

**Confirm the SNS subscription** — AWS emails `richard.sarfo@amalitech.com` (or whatever `TF_VAR_alert_email` is set to). Click the confirmation link or no failure alerts will arrive.

## 4. Disable EventBridge before the first upload

The state machine processes all three datasets regardless of which file triggered it. Uploading three files therefore fires three concurrent executions — they race on Delta MERGEs and break archiving. For the first run, fire one execution manually:

```bash
docker run --rm --env-file .env amazon/aws-cli:latest events disable-rule --name lh-dev-raw-upload
```

## 5. Upload + trigger

```bash
make upload         # pushes 3 CSVs to s3://<bucket>/raw/{dataset}/
make trigger        # starts one Step Functions execution
```

Watch in the console: **States → State machines → lh-dev-lakehouse-pipeline**.

Expected timing: ~3–4 min total (Glue cold starts dominate).

## 6. Verify

```bash
make query
```

Expected: `products=1000, orders=500, order_items=2768`.

## 7. Re-enable EventBridge

After the first successful execution, file drops should auto-trigger:

```bash
docker run --rm --env-file .env amazon/aws-cli:latest events enable-rule --name lh-dev-raw-upload
```

---

## Gotchas encountered during first live apply

These are now baked into the Terraform config but documented here for posterity.

### Glue Step Functions ARN

`arn:aws:states:::glue:startJobRun.sync:2` is **rejected at create time** with `SCHEMA_VALIDATION_FAILED`. The `:N` payload-version suffix is reserved for `lambda:invoke`; the Glue optimized integration uses the plain `.sync` form. Fixed in [terraform/step_functions.tf](terraform/step_functions.tf).

### `--extra-py-files` flattens packages

Listing individual `lib/*.py` files via `--extra-py-files` makes each importable as a top-level module (`import config`) but **not** as a package (`from lib.config import ...`). Solution: package as `lib.zip` via `data "archive_file"`. Fixed in [terraform/s3.tf](terraform/s3.tf).

### Athena needs bucket-level S3 perms

`s3:GetObject` / `PutObject` on `bucket/*` is not enough — Athena calls `s3:ListBucket` and `s3:GetBucketLocation` on the bucket ARN itself before issuing a query. Without these, queries fail with `Unable to verify/create output bucket`. Fixed in [terraform/iam.tf](terraform/iam.tf).

### Glue Catalog must match Athena DDL exactly

`table_type=DELTA` (upper-case) plus a top-level `path` parameter looks correct in the Glue console but Athena's native Delta reader **rejects it**. The shape that works (reverse-engineered by reading a table created via Athena DDL):

- `table_type=delta` (lowercase)
- `EXTERNAL=TRUE`
- `spark.sql.sources.provider=delta`
- `spark.sql.partitionProvider=catalog`
- `spark.sql.sources.schema.numParts=1`
- `spark.sql.sources.schema.part.0=<JSON-serialized Spark struct schema>`
- `path` on the **SerDe parameters**, not the table parameters
- No `classification` key

Fixed in [terraform/glue_catalog.tf](terraform/glue_catalog.tf).

### GitHub OIDC provider doesn't exist by default

A fresh AWS account has zero IAM OIDC providers. The Terraform config originally used a `data "aws_iam_openid_connect_provider"` lookup that fails at plan time. Switched to a managed `resource` so the provider is created on first apply. Fixed in [terraform/iam.tf](terraform/iam.tf).

### PowerShell mangles `-out=tfplan.bin`

Terraform invocations like `docker run … hashicorp/terraform plan -out=tfplan.bin` produce `Error: Too many command line arguments` under PowerShell because the `=` is parsed as separating arguments. Workaround: run under Git Bash with `MSYS_NO_PATHCONV=1` (Makefile already does this).

---

## Tear-down

```bash
make tf-destroy
```

This removes all 34 resources. The S3 bucket is `force_destroy = true` under non-prod environments, so it'll empty itself.

---

## Cost note

At rest (no executions): a few cents per month for the SNS topic, the Athena workgroup, and minimal S3 storage of the Delta tables. Per-execution cost is dominated by Glue DPUs (~$0.44/DPU-hour × 2 workers × ~3 min per dataset × 3 datasets ≈ $0.13/run).
