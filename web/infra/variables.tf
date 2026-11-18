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

variable "upload_retention_days" {
  description = "Days an uploaded backup is stored before the bucket's rule deletes it. The app shows this date, so set the same number as the UPLOAD_RETENTION_DAYS repository variable the deploy passes to the service (default 30)."
  type        = number
  default     = 30
}
