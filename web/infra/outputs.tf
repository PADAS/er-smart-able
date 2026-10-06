output "wif_provider" {
  description = "WIF provider resource name (GCP_WIF_PROVIDER)"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deploy_service_account" {
  description = "Deploy service account (GCP_SERVICE_ACCOUNT)"
  value       = google_service_account.deploy.email
}

output "runtime_service_account" {
  description = "Runtime service account for the service and the job"
  value       = google_service_account.runtime.email
}

output "ar_repository" {
  description = "Artifact Registry repository (AR_REPOSITORY)"
  value       = google_artifact_registry_repository.docker.repository_id
}

output "bucket" {
  description = "Data bucket (GCS_BUCKET)"
  value       = google_storage_bucket.data.name
}
