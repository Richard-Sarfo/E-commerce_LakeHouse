# Changelog

All notable changes to this project. Format loosely based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Local pre-commit hooks (`.pre-commit-config.yaml`) mirroring CI checks: ruff, terraform fmt/validate, credential-leak detection, YAML/JSON syntax, large-file guard.
- Onboarding: `.env.example` template, `Makefile` wrapping Docker-based Terraform and AWS operations, and `DEPLOYMENT.md` runbook capturing every gotcha from the first live apply.
- `github_repo` Terraform variable allowing the OIDC trust policy to be pinned to a specific `<org>/<repo>` instead of the original `repo:*` wildcard. Defaults to `*/*` for backwards compatibility.
- Two new Athena analytical queries: top customers by lifetime value (`05_top_customers.sql`) and department-pair basket co-occurrence (`06_department_basket_pairs.sql`).
- Type hints, expanded docstrings, and the missing `Column` import in `glue_jobs/lib/validation.py` and `glue_jobs/lib/delta_io.py`.

### Changed

- OIDC trust policy now requires both `sub` (repo/branch) **and** `aud=sts.amazonaws.com` conditions; previously only `sub` was checked.

## [0.1.0] — 2026-06-04 — Live deployment

First end-to-end deployment to AWS account `982081084448` (region `us-east-1`). Pipeline ingests three sample April-2025 datasets into Delta Lake tables queryable via Athena.

### Added

- Step Functions state machine, EventBridge rule, SNS alerts (`terraform/{step_functions,eventbridge,sns}.tf`).
- Glue jobs: parametrized `transform_dataset.py` plus Python-shell `archive_files.py`.
- Glue Data Catalog tables matching the exact shape Athena's native Delta reader expects.
- Athena workgroup pinned to engine v3 with SSE-S3 result encryption.
- GitHub Actions `ci.yml` (lint + pytest + terraform validate) and `deploy.yml` (OIDC → terraform apply on main).
- Unit tests for `validation.py` and `delta_io.py` running in a `apache/spark:3.5.0-python3` container — 11 tests, all green.

### Fixed (post-apply)

- Step Functions `glue:startJobRun.sync:2` ARN rejected at create time — dropped the `:2` payload-version suffix.
- Glue `--extra-py-files` flattened individual `.py` files breaking `from lib.config import …` — repackaged as `lib.zip` via `data "archive_file"`.
- SFN role lacked bucket-level S3 permissions Athena needs (`s3:ListBucket`, `s3:GetBucketLocation`) — added an `S3BucketLevel` IAM statement.
- Glue Catalog tables registered with `table_type=DELTA` (upper case) and a top-level `path` parameter were not recognized as Delta by Athena — restructured to the exact shape Athena DDL produces: lowercase `table_type=delta`, schema JSON in `spark.sql.sources.schema.part.0`, `path` on the SerDe parameters.
- Fresh accounts have no GitHub OIDC provider — switched from `data` source to managed `resource`.

### Verified

| Dataset | Rows |
|---|---|
| `products` | 1,000 |
| `orders` | 500 |
| `order_items` | 2,768 |

3-way join (`order_items ⨝ orders ⨝ products`) returns expected results.
