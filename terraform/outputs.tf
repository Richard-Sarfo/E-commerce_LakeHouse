output "bucket_name" {
  description = "S3 bucket used for all zones (raw, processed, archived, rejected)"
  value       = aws_s3_bucket.data.id
}

output "glue_database" {
  description = "Glue Data Catalog database name (use in Athena FROM clause)"
  value       = aws_glue_catalog_database.lakehouse.name
}

output "state_machine_arn" {
  description = "ARN of the Step Functions state machine"
  value       = aws_sfn_state_machine.lakehouse.arn
}

output "athena_workgroup" {
  description = "Athena workgroup name"
  value       = aws_athena_workgroup.lakehouse.name
}

output "github_actions_role_arn" {
  description = "IAM role ARN to set as AWS_ROLE_TO_ASSUME in GitHub Actions secrets"
  value       = aws_iam_role.github_actions.arn
}

output "manual_trigger_command" {
  description = "AWS CLI command to manually trigger the pipeline for a demo run"
  value = <<-EOT
    aws stepfunctions start-execution \
      --state-machine-arn ${aws_sfn_state_machine.lakehouse.arn} \
      --input '{"bucket":"${aws_s3_bucket.data.id}","key":"raw/orders/orders_apr_2025.csv"}'
  EOT
}
