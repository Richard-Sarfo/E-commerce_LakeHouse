# ── Glue Database ────────────────────────────────────────────────────────────

resource "aws_glue_catalog_database" "lakehouse" {
  name        = "${local.name_prefix}_lakehouse"
  description = "E-commerce lakehouse — Delta tables queryable via Athena"
}

# ── Shared job defaults ──────────────────────────────────────────────────────

locals {
  glue_common_args = {
    "--TempDir"                          = local.glue_temp
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--job-language"                     = "python"
    "--datalake-formats"                 = "delta" # enables Delta Lake on Glue 4.0
    "--extra-py-files"                   = "s3://${aws_s3_bucket.data.id}/${aws_s3_object.lib_zip.key}"
    "--processed_root"                   = local.processed_root
    "--rejected_root"                    = local.rejected_root
  }
}

# ── transform_dataset — one job handles all three datasets ───────────────────

resource "aws_glue_job" "transform" {
  name              = "${local.name_prefix}-transform-dataset"
  role_arn          = aws_iam_role.glue.arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 30 # minutes

  execution_property {
    max_concurrent_runs = 3 # products + orders + order_items can overlap
  }

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${aws_s3_bucket.data.id}/${aws_s3_object.transform_script.key}"
  }

  default_arguments = local.glue_common_args
}

# ── archive_files — Python-shell, no Spark needed ────────────────────────────

resource "aws_glue_job" "archive" {
  name         = "${local.name_prefix}-archive-files"
  role_arn     = aws_iam_role.glue.arn
  glue_version = "4.0"
  max_capacity = 0.0625 # DPU for Python shell

  command {
    name            = "pythonshell"
    python_version  = "3.9"
    script_location = "s3://${aws_s3_bucket.data.id}/${aws_s3_object.archive_script.key}"
  }

  default_arguments = {
    "--TempDir"                          = local.glue_temp
    "--enable-continuous-cloudwatch-log" = "true"
    "--bucket"                           = aws_s3_bucket.data.id
  }
}
