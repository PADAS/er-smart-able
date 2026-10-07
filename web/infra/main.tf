# smart-able on GCP, in the pattern of PADAS/gundi-webhook-editor: Artifact
# Registry for the two images, a deploy service account reached through
# Workload Identity Federation from GitHub Actions, a runtime service account
# shared by the Cloud Run service and the extraction Job, Firestore for the
# dataset index, and a private bucket for uploads and extracted sites.
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  apis = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "firestore.googleapis.com",
    "storage.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

# --- images ---
resource "google_artifact_registry_repository" "docker" {
  location      = var.region
  repository_id = "smart-able"
  format        = "DOCKER"
  description   = "smart-able service and extraction job images"
  depends_on    = [google_project_service.apis]
}

# --- service accounts ---
resource "google_service_account" "deploy" {
  account_id   = "smart-able-deploy"
  display_name = "smart-able GitHub Actions deploy"
  depends_on   = [google_project_service.apis]
}

resource "google_service_account" "runtime" {
  account_id   = "smart-able-runtime"
  display_name = "smart-able service and job runtime"
  depends_on   = [google_project_service.apis]
}

locals {
  deploy_roles = [
    "roles/artifactregistry.writer",
    "roles/run.admin",
    "roles/iam.serviceAccountUser",
  ]
  runtime_roles = [
    "roles/datastore.user", # Firestore: the dataset index
    "roles/run.developer",  # start executions of the extraction job
  ]
}

resource "google_project_iam_member" "deploy" {
  for_each = toset(local.deploy_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_project_iam_member" "runtime" {
  for_each = toset(local.runtime_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.runtime.email}"
}

# the service signs upload URLs with its own identity (no key file), and
# starting a job execution means acting as the job's service account
resource "google_service_account_iam_member" "runtime_self" {
  for_each           = toset(["roles/iam.serviceAccountTokenCreator", "roles/iam.serviceAccountUser"])
  service_account_id = google_service_account.runtime.name
  role               = each.value
  member             = "serviceAccount:${google_service_account.runtime.email}"
}

# --- Workload Identity Federation for GitHub Actions ---
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "smart-able-github-pool"
  display_name              = "smart-able GitHub Actions"
  depends_on                = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions-provider"
  display_name                       = "GitHub Actions Provider"
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }
  attribute_condition = "assertion.repository == \"${var.github_repo}\""
}

resource "google_service_account_iam_member" "wif_deploy" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}

# --- Firestore (dataset index) ---
# If the project already has a (default) database (gundi-webhook-editor's), import it:
#   tofu import google_firestore_database.default "projects/<project>/databases/(default)"
resource "google_firestore_database" "default" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_project_service.apis]
}

# --- bucket: uploads and extracted sites, private, browser PUTs by signed URL ---
resource "google_storage_bucket" "data" {
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  cors {
    origin          = ["*"]
    method          = ["PUT"]
    response_header = ["Content-Type"]
    max_age_seconds = 3600
  }

  lifecycle_rule {
    # an uploaded backup is only needed until it has been extracted
    condition {
      age            = 30
      matches_prefix = ["datasets/"]
      matches_suffix = [".zip", ".bak"]
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket_iam_member" "runtime" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runtime.email}"
}
