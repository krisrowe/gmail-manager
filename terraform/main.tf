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

# =============================================================================
# Enable Required APIs
# =============================================================================

resource "google_project_service" "run" {
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "scheduler" {
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "secretmanager" {
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "artifactregistry" {
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloudbuild" {
  service            = "cloudbuild.googleapis.com"
  disable_on_destroy = false
}

# =============================================================================
# Service Account
# =============================================================================

resource "google_service_account" "gmail_manager" {
  account_id   = "gmail-manager-runner"
  display_name = "Gmail Manager Cloud Run Runner"
}

# =============================================================================
# Secrets
# =============================================================================

resource "google_secret_manager_secret" "user_token" {
  secret_id = "gmail-manager-user-token"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret" "config" {
  secret_id = "gmail-manager-config"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

# Initial secret values from local files (only created once, ignored after)
resource "google_secret_manager_secret_version" "user_token_initial" {
  secret      = google_secret_manager_secret.user_token.id
  secret_data = file(var.local_token_path)

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Config is managed by terraform - local changes are synced to Secrets Manager on apply
resource "google_secret_manager_secret_version" "config" {
  secret      = google_secret_manager_secret.config.id
  secret_data = file(var.local_config_path)
}

# =============================================================================
# Secret IAM Bindings
# =============================================================================

resource "google_secret_manager_secret_iam_member" "token_accessor" {
  secret_id = google_secret_manager_secret.user_token.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.gmail_manager.email}"
}

resource "google_secret_manager_secret_iam_member" "token_version_adder" {
  secret_id = google_secret_manager_secret.user_token.secret_id
  role      = "roles/secretmanager.secretVersionAdder"
  member    = "serviceAccount:${google_service_account.gmail_manager.email}"
}

resource "google_secret_manager_secret_iam_member" "config_accessor" {
  secret_id = google_secret_manager_secret.config.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.gmail_manager.email}"
}

# =============================================================================
# Artifact Registry (for Docker images)
# =============================================================================

resource "google_artifact_registry_repository" "gmail_manager" {
  location      = var.region
  repository_id = "gmail-manager"
  format        = "DOCKER"

  depends_on = [google_project_service.artifactregistry]
}

# =============================================================================
# Build and Push Docker Image via Cloud Build
# =============================================================================

resource "null_resource" "docker_build" {
  count = var.skip_build ? 0 : 1

  triggers = {
    dockerfile_hash = filemd5("${path.module}/../Dockerfile")
    source_hash     = sha256(join("", [for f in fileset("${path.module}/..", "*.py") : filemd5("${path.module}/../${f}")]))
  }

  provisioner "local-exec" {
    working_dir = "${path.module}/.."
    command     = "gcloud builds submit --project=${var.project_id} --tag ${var.region}-docker.pkg.dev/${var.project_id}/gmail-manager/gmail-manager:latest"
  }

  depends_on = [google_artifact_registry_repository.gmail_manager, google_project_service.cloudbuild]
}

# =============================================================================
# Cloud Run Job
# =============================================================================

resource "google_cloud_run_v2_job" "gmail_manager" {
  name     = "gmail-manager"
  location = var.region

  template {
    template {
      service_account = google_service_account.gmail_manager.email

      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/gmail-manager/gmail-manager:latest"

        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }

      # Allow up to 15 minutes for email processing
      timeout = "900s"
    }
  }

  depends_on = [google_project_service.run]
}

# =============================================================================
# Cloud Scheduler
# =============================================================================

resource "google_cloud_scheduler_job" "gmail_manager_trigger" {
  name        = "gmail-manager-trigger"
  description = "Trigger Gmail Manager every 6 hours"
  schedule    = var.schedule
  time_zone   = "America/Chicago"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.gmail_manager.name}:run"

    oauth_token {
      service_account_email = "${data.google_project.current.number}-compute@developer.gserviceaccount.com"
    }
  }

  retry_config {
    retry_count = 1
  }

  depends_on = [google_project_service.scheduler]
}

data "google_project" "current" {
  project_id = var.project_id
}

# Allow default compute SA to invoke Cloud Run Jobs
#
# Security note: Using the default compute SA for invocation is safe because
# the job takes no arguments and always performs the same operation. If the job
# were parameterized (e.g., accepting different configs, rules, or targets),
# invocation would need stricter access control with a dedicated service account.
resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  name     = google_cloud_run_v2_job.gmail_manager.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com"
}
