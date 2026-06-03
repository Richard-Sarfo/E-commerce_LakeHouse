locals {
  account_id  = data.aws_caller_identity.current.account_id
  region      = data.aws_region.current.name
  name_prefix = "${var.project_prefix}-${var.environment}"

  bucket_name = "${local.name_prefix}-lakehouse-${local.account_id}"

  # Datasets and their raw CSV file names — used to drive Glue job arguments
  datasets = {
    products    = "products.csv"
    orders      = "orders_apr_2025.csv"
    order_items = "order_items_apr_2025.csv"
  }

  # S3 path roots
  processed_root = "s3://${local.bucket_name}/processed"
  rejected_root  = "s3://${local.bucket_name}/rejected"
  glue_temp      = "s3://${local.bucket_name}/glue-temp"
  athena_results = "s3://${local.bucket_name}/athena-results"
}
