# EventBridge rule: trigger the Step Functions pipeline when a CSV lands
# in any of the three raw/{dataset}/ prefixes.

resource "aws_cloudwatch_event_rule" "raw_upload" {
  name        = "${local.name_prefix}-raw-upload"
  description = "Fires when a CSV is uploaded to the raw/ S3 prefix"

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = {
        name = [aws_s3_bucket.data.id]
      }
      object = {
        key = [{ prefix = "raw/" }]
      }
    }
  })
}

resource "aws_cloudwatch_event_target" "sfn" {
  rule     = aws_cloudwatch_event_rule.raw_upload.name
  arn      = aws_sfn_state_machine.lakehouse.arn
  role_arn = aws_iam_role.eventbridge.arn

  # Pass bucket name and object key to the state machine as the input
  input_transformer {
    input_paths = {
      bucket = "$.detail.bucket.name"
      key    = "$.detail.object.key"
    }
    input_template = "{\"bucket\": \"<bucket>\", \"key\": \"<key>\"}"
  }
}
