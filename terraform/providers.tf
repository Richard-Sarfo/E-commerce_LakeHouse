terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  # Partial backend config — `bucket`, `key`, `region` are supplied at init
  # time via `-backend-config=` flags (see .github/workflows/deploy.yml and
  # the Makefile). This declaration is required so the flags are actually
  # honoured; without it Terraform silently falls back to local state and
  # every CI run starts from scratch.
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "lakehouse-ecommerce"
      ManagedBy   = "terraform"
      Environment = var.environment
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
