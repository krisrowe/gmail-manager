output "cloud_run_job_name" {
  description = "Name of the Cloud Run Job"
  value       = google_cloud_run_v2_job.gmail_manager.name
}

output "scheduler_job_name" {
  description = "Name of the Cloud Scheduler job"
  value       = google_cloud_scheduler_job.gmail_manager_trigger.name
}

output "service_account_email" {
  description = "Service account email used by Cloud Run"
  value       = google_service_account.gmail_manager.email
}

output "artifact_registry_url" {
  description = "Artifact Registry URL for Docker images"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.gmail_manager.repository_id}"
}
