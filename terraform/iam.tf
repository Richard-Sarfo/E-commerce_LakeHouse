# ── Glue execution role ─────────────────────────────────────────────────────

data "aws_iam_policy_document" "glue_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "glue" {
  name               = "${local.name_prefix}-glue-role"
  assume_role_policy = data.aws_iam_policy_document.glue_assume.json
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

data "aws_iam_policy_document" "glue_s3" {
  statement {
    sid     = "BucketAccess"
    effect  = "Allow"
    actions = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.data.arn]
  }
  statement {
    sid    = "ObjectAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:CopyObject",
    ]
    resources = ["${aws_s3_bucket.data.arn}/*"]
  }
  statement {
    sid     = "CloudWatchMetrics"
    effect  = "Allow"
    actions = ["cloudwatch:PutMetricData"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "glue_s3" {
  name   = "s3-and-cloudwatch"
  role   = aws_iam_role.glue.id
  policy = data.aws_iam_policy_document.glue_s3.json
}

# ── Step Functions execution role ────────────────────────────────────────────

data "aws_iam_policy_document" "sfn_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sfn" {
  name               = "${local.name_prefix}-sfn-role"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume.json
}

data "aws_iam_policy_document" "sfn_permissions" {
  statement {
    sid     = "StartGlueJobs"
    effect  = "Allow"
    actions = ["glue:StartJobRun", "glue:GetJobRun", "glue:GetJobRuns", "glue:BatchStopJobRun"]
    resources = ["*"]
  }
  statement {
    sid     = "S3Archive"
    effect  = "Allow"
    actions = ["s3:CopyObject", "s3:DeleteObject", "s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.data.arn}/*"]
  }
  statement {
    sid     = "AthenaValidation"
    effect  = "Allow"
    actions = [
      "athena:StartQueryExecution",
      "athena:GetQueryExecution",
      "athena:GetQueryResults",
    ]
    resources = ["*"]
  }
  statement {
    sid     = "GlueCatalogRead"
    effect  = "Allow"
    actions = ["glue:GetTable", "glue:GetDatabase"]
    resources = ["*"]
  }
  statement {
    sid     = "SNSPublish"
    effect  = "Allow"
    actions = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
  }
  statement {
    sid     = "CloudWatchLogs"
    effect  = "Allow"
    actions = ["logs:CreateLogDelivery", "logs:GetLogDelivery", "logs:UpdateLogDelivery",
               "logs:DeleteLogDelivery", "logs:ListLogDeliveries",
               "logs:PutResourcePolicy", "logs:DescribeResourcePolicies",
               "logs:DescribeLogGroups"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "sfn" {
  name   = "sfn-permissions"
  role   = aws_iam_role.sfn.id
  policy = data.aws_iam_policy_document.sfn_permissions.json
}

# ── EventBridge role to trigger Step Functions ───────────────────────────────

data "aws_iam_policy_document" "eb_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eventbridge" {
  name               = "${local.name_prefix}-eb-role"
  assume_role_policy = data.aws_iam_policy_document.eb_assume.json
}

data "aws_iam_policy_document" "eb_sfn" {
  statement {
    effect  = "Allow"
    actions = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.lakehouse.arn]
  }
}

resource "aws_iam_role_policy" "eb_sfn" {
  name   = "start-sfn"
  role   = aws_iam_role.eventbridge.id
  policy = data.aws_iam_policy_document.eb_sfn.json
}

# ── GitHub Actions OIDC (no long-lived access keys in CI) ───────────────────

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]
}

data "aws_iam_policy_document" "github_oidc_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:*:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "${local.name_prefix}-github-actions-role"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_assume.json
}

data "aws_iam_policy_document" "github_deploy" {
  statement {
    sid    = "TerraformState"
    effect = "Allow"
    actions = [
      "s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:DeleteObject",
    ]
    resources = [
      aws_s3_bucket.data.arn,
      "${aws_s3_bucket.data.arn}/*",
    ]
  }
  statement {
    sid     = "ManageInfra"
    effect  = "Allow"
    actions = ["glue:*", "states:*", "iam:PassRole", "events:*", "sns:*", "athena:*"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  name   = "deploy-permissions"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_deploy.json
}
