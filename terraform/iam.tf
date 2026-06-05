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
    sid       = "BucketAccess"
    effect    = "Allow"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
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
    sid       = "CloudWatchMetrics"
    effect    = "Allow"
    actions   = ["cloudwatch:PutMetricData"]
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
    sid       = "StartGlueJobs"
    effect    = "Allow"
    actions   = ["glue:StartJobRun", "glue:GetJobRun", "glue:GetJobRuns", "glue:BatchStopJobRun"]
    resources = ["*"]
  }
  statement {
    sid       = "S3Archive"
    effect    = "Allow"
    actions   = ["s3:CopyObject", "s3:DeleteObject", "s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.data.arn}/*"]
  }
  statement {
    sid       = "S3BucketLevel"
    effect    = "Allow"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.data.arn]
  }
  statement {
    sid    = "AthenaValidation"
    effect = "Allow"
    actions = [
      "athena:StartQueryExecution",
      "athena:GetQueryExecution",
      "athena:GetQueryResults",
    ]
    resources = ["*"]
  }
  statement {
    sid       = "GlueCatalogRead"
    effect    = "Allow"
    actions   = ["glue:GetTable", "glue:GetDatabase"]
    resources = ["*"]
  }
  statement {
    sid       = "SNSPublish"
    effect    = "Allow"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
  }
  statement {
    sid    = "CloudWatchLogs"
    effect = "Allow"
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
    effect    = "Allow"
    actions   = ["states:StartExecution"]
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
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]

  # Bootstrap resource — without it GitHub Actions cannot assume any role.
  # Block accidental destruction so `make tf-destroy` doesn't break the
  # deploy workflow's ability to re-create everything else.
  lifecycle {
    prevent_destroy = true
  }
}

data "aws_iam_policy_document" "github_oidc_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    # Restrict to a specific repo + branch. Default github_repo="*/*"
    # preserves the legacy permissive behaviour; setting it to
    # "your-org/your-repo" pins the trust to that repository's main
    # branch only — recommended for any non-throwaway deployment.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/main"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "${local.name_prefix}-github-actions-role"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_assume.json
}

data "aws_iam_policy_document" "github_deploy" {
  # S3 — full access scoped to our own buckets (data + state).
  #
  # We intentionally use s3:* rather than an enumerated allow-list. Terraform's
  # AWS provider reads every bucket sub-attribute on `plan` — accelerate,
  # replication, intelligent-tiering, analytics, metrics, inventory,
  # ownership-controls, request-payment, and more — and AWS's IAM action
  # naming is inconsistent (some end with `Configuration`, others with
  # `BucketConfiguration`). Wildcarding the catalog is operationally cheaper
  # than maintaining the list, and the resource-ARN scope (`lh-*`) keeps the
  # blast radius bounded: this role still can't touch any non-project bucket.
  statement {
    sid     = "ManageProjectBuckets"
    effect  = "Allow"
    actions = ["s3:*"]
    resources = [
      "arn:aws:s3:::lh-*",
      "arn:aws:s3:::lh-*/*",
    ]
  }

  # IAM — Terraform manages Glue, SFN, EventBridge service roles and
  # this very deploy role. Scoped to the project naming convention.
  statement {
    sid    = "ManageIAMRoles"
    effect = "Allow"
    actions = [
      "iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:UpdateRole",
      "iam:UpdateAssumeRolePolicy", "iam:TagRole", "iam:UntagRole",
      "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:GetRolePolicy",
      "iam:ListRolePolicies",
      "iam:AttachRolePolicy", "iam:DetachRolePolicy",
      "iam:ListAttachedRolePolicies", "iam:ListInstanceProfilesForRole",
      "iam:PassRole",
    ]
    resources = [
      "arn:aws:iam::${local.account_id}:role/lh-*",
    ]
  }

  # IAM OIDC provider — read-only on the GitHub provider so plan can
  # confirm it exists. Mutation is blocked by `prevent_destroy` and we
  # don't grant Create/Delete here so even a compromised role can't
  # tamper with the trust anchor.
  statement {
    sid    = "ReadOIDCProvider"
    effect = "Allow"
    actions = [
      "iam:GetOpenIDConnectProvider", "iam:ListOpenIDConnectProviders",
      "iam:TagOpenIDConnectProvider", "iam:UntagOpenIDConnectProvider",
    ]
    resources = ["*"]
  }

  # CloudWatch Logs — SFN log group and Glue continuous logging.
  statement {
    sid    = "ManageCloudWatchLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup", "logs:DeleteLogGroup",
      "logs:DescribeLogGroups", "logs:TagResource", "logs:UntagResource",
      "logs:ListTagsForResource", "logs:PutRetentionPolicy",
      "logs:DeleteRetentionPolicy",
    ]
    resources = ["*"]
  }

  # All the data-plane services Terraform creates and manages.
  statement {
    sid       = "ManageDataPlaneServices"
    effect    = "Allow"
    actions   = ["glue:*", "states:*", "events:*", "sns:*", "athena:*"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  name   = "deploy-permissions"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_deploy.json
}
