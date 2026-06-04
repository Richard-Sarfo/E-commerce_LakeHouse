variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (dev / staging / prod)"
  type        = string
  default     = "dev"
}

variable "project_prefix" {
  description = "Short prefix used in resource names to avoid global-name collisions"
  type        = string
  default     = "lh"
}

variable "alert_email" {
  description = "Email address for SNS failure alerts"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository allowed to assume the deploy role, in <org>/<repo> form. The OIDC trust policy restricts AssumeRoleWithWebIdentity to refs/heads/main of this repo only."
  type        = string
  default     = "*/*"
}
