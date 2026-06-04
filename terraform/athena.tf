resource "aws_athena_workgroup" "lakehouse" {
  name          = "${local.name_prefix}-lakehouse"
  description   = "Athena workgroup for e-commerce lakehouse queries"
  force_destroy = var.environment != "prod"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    engine_version {
      selected_engine_version = "Athena engine version 3"
    }
    result_configuration {
      output_location = local.athena_results
      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}
