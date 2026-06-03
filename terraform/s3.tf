resource "aws_s3_bucket" "data" {
  bucket        = local.bucket_name
  force_destroy = var.environment != "prod"
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable EventBridge notifications so S3 PutObject events flow to the rule
resource "aws_s3_bucket_notification" "data" {
  bucket      = aws_s3_bucket.data.id
  eventbridge = true
}

# Upload Glue ETL scripts — etag ensures re-upload only on content change
resource "aws_s3_object" "transform_script" {
  bucket = aws_s3_bucket.data.id
  key    = "glue-scripts/transform_dataset.py"
  source = "${path.module}/../glue_jobs/transform_dataset.py"
  etag   = filemd5("${path.module}/../glue_jobs/transform_dataset.py")
}

resource "aws_s3_object" "archive_script" {
  bucket = aws_s3_bucket.data.id
  key    = "glue-scripts/archive_files.py"
  source = "${path.module}/../glue_jobs/archive_files.py"
  etag   = filemd5("${path.module}/../glue_jobs/archive_files.py")
}

# Upload lib modules so Glue workers can import them
resource "aws_s3_object" "lib_config" {
  bucket = aws_s3_bucket.data.id
  key    = "glue-scripts/lib/config.py"
  source = "${path.module}/../glue_jobs/lib/config.py"
  etag   = filemd5("${path.module}/../glue_jobs/lib/config.py")
}

resource "aws_s3_object" "lib_validation" {
  bucket = aws_s3_bucket.data.id
  key    = "glue-scripts/lib/validation.py"
  source = "${path.module}/../glue_jobs/lib/validation.py"
  etag   = filemd5("${path.module}/../glue_jobs/lib/validation.py")
}

resource "aws_s3_object" "lib_delta_io" {
  bucket = aws_s3_bucket.data.id
  key    = "glue-scripts/lib/delta_io.py"
  source = "${path.module}/../glue_jobs/lib/delta_io.py"
  etag   = filemd5("${path.module}/../glue_jobs/lib/delta_io.py")
}

resource "aws_s3_object" "lib_init" {
  bucket  = aws_s3_bucket.data.id
  key     = "glue-scripts/lib/__init__.py"
  content = ""
  etag    = md5("")
}
