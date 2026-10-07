variable "project_id" {
  description = "GCP project"
  type        = string
}

variable "region" {
  description = "Region for Cloud Run, Artifact Registry, Firestore and the bucket"
  type        = string
  default     = "us-central1"
}

variable "github_repo" {
  description = "owner/repo allowed to deploy through Workload Identity Federation"
  type        = string
}

variable "bucket_name" {
  description = "GCS bucket for uploaded backups and extracted sites (globally unique)"
  type        = string
}
