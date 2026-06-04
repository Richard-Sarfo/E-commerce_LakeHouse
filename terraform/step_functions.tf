locals {
  sfn_definition = jsonencode({
    Comment = "E-commerce lakehouse ETL: validate, transform, merge, archive, verify"
    StartAt = "TransformParallel"
    TimeoutSeconds = 3600

    States = {

      # ── Step 1: products and orders run in parallel (no cross-dependency) ──
      TransformParallel = {
        Type    = "Parallel"
        Comment = "Run products and orders ETL concurrently"
        Branches = [
          {
            StartAt = "TransformProducts"
            States = {
              TransformProducts = {
                Type     = "Task"
                Resource = "arn:aws:states:::glue:startJobRun.sync"
                Parameters = {
                  JobName = aws_glue_job.transform.name
                  Arguments = {
                    "--dataset"   = "products"
                    "--input_s3"  = "s3://${aws_s3_bucket.data.id}/raw/products/products.csv"
                    "--run_id.$"  = "$$.Execution.Name"
                  }
                }
                TimeoutSeconds = 1800
                Retry = [{
                  ErrorEquals     = ["Glue.ConcurrentRunsExceededException"]
                  IntervalSeconds = 30
                  MaxAttempts     = 5
                  BackoffRate     = 2.0
                }]
                Catch = [{
                  ErrorEquals = ["States.ALL"]
                  Next        = "ProductsFailed"
                  ResultPath  = "$.error"
                }]
                ResultPath = "$.products"
                End        = true
              }
              ProductsFailed = {
                Type  = "Fail"
                Cause = "Products ETL job failed"
              }
            }
          },
          {
            StartAt = "TransformOrders"
            States = {
              TransformOrders = {
                Type     = "Task"
                Resource = "arn:aws:states:::glue:startJobRun.sync"
                Parameters = {
                  JobName = aws_glue_job.transform.name
                  Arguments = {
                    "--dataset"   = "orders"
                    "--input_s3"  = "s3://${aws_s3_bucket.data.id}/raw/orders/orders_apr_2025.csv"
                    "--run_id.$"  = "$$.Execution.Name"
                  }
                }
                TimeoutSeconds = 1800
                Retry = [{
                  ErrorEquals     = ["Glue.ConcurrentRunsExceededException"]
                  IntervalSeconds = 30
                  MaxAttempts     = 5
                  BackoffRate     = 2.0
                }]
                Catch = [{
                  ErrorEquals = ["States.ALL"]
                  Next        = "OrdersFailed"
                  ResultPath  = "$.error"
                }]
                ResultPath = "$.orders"
                End        = true
              }
              OrdersFailed = {
                Type  = "Fail"
                Cause = "Orders ETL job failed"
              }
            }
          }
        ]

        ResultPath = "$.parallel_results"
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "NotifyFailure"
          ResultPath  = "$.error"
        }]
        Next = "TransformOrderItems"
      }

      # ── Step 2: order_items — requires products + orders to be present first ──
      TransformOrderItems = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = aws_glue_job.transform.name
          Arguments = {
            "--dataset"   = "order_items"
            "--input_s3"  = "s3://${aws_s3_bucket.data.id}/raw/order_items/order_items_apr_2025.csv"
            "--run_id.$"  = "$$.Execution.Name"
          }
        }
        TimeoutSeconds = 1800
        Retry = [{
          ErrorEquals     = ["Glue.ConcurrentRunsExceededException"]
          IntervalSeconds = 30
          MaxAttempts     = 5
          BackoffRate     = 2.0
        }]
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "NotifyFailure"
          ResultPath  = "$.error"
        }]
        ResultPath = "$.order_items"
        Next       = "ArchiveFiles"
      }

      # ── Step 3: archive raw files ─────────────────────────────────────────
      ArchiveFiles = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = aws_glue_job.archive.name
          Arguments = {
            "--raw_keys"      = "raw/products/products.csv,raw/orders/orders_apr_2025.csv,raw/order_items/order_items_apr_2025.csv"
            "--archive_date.$" = "$$.Execution.StartTime"
          }
        }
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "NotifyFailure"
          ResultPath  = "$.error"
        }]
        ResultPath = "$.archive"
        Next       = "ValidatePresence"
      }

      # ── Step 4: Athena spot-check ─────────────────────────────────────────
      ValidatePresence = {
        Type     = "Task"
        Resource = "arn:aws:states:::athena:startQueryExecution.sync"
        Parameters = {
          QueryString       = "SELECT COUNT(*) AS orders_count FROM ${aws_glue_catalog_database.lakehouse.name}.orders"
          WorkGroup         = aws_athena_workgroup.lakehouse.name
          ResultConfiguration = {
            OutputLocation = "${local.athena_results}/validation/"
          }
        }
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "NotifyFailure"
          ResultPath  = "$.error"
        }]
        ResultPath = "$.validation"
        Next       = "Succeed"
      }

      # ── Terminal: success ─────────────────────────────────────────────────
      Succeed = {
        Type = "Succeed"
      }

      # ── Terminal: failure — notify then fail ──────────────────────────────
      NotifyFailure = {
        Type     = "Task"
        Resource = "arn:aws:states:::sns:publish"
        Parameters = {
          TopicArn    = aws_sns_topic.alerts.arn
          Subject     = "Lakehouse pipeline failure"
          "Message.$" = "States.JsonToString($)"
        }
        ResultPath = "$.notification"
        Next       = "FailExecution"
      }

      FailExecution = {
        Type  = "Fail"
        Cause = "Pipeline failed — see SNS notification for details"
      }
    }
  })
}

resource "aws_sfn_state_machine" "lakehouse" {
  name     = "${local.name_prefix}-lakehouse-pipeline"
  role_arn = aws_iam_role.sfn.arn
  definition = local.sfn_definition

  logging_configuration {
    level                  = "ERROR"
    include_execution_data = true
    log_destination        = "${aws_cloudwatch_log_group.sfn.arn}:*"
  }
}

resource "aws_cloudwatch_log_group" "sfn" {
  name              = "/aws/states/${local.name_prefix}-lakehouse-pipeline"
  retention_in_days = 30
}
