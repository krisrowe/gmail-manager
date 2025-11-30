variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run"
  type        = string
  default     = "us-central1"
}

variable "schedule" {
  description = "Cloud Scheduler cron expression"
  type        = string
  default     = "0 */6 * * *" # Every 6 hours
}

variable "local_token_path" {
  description = "Path to local user_token.json file"
  type        = string
  default     = "~/.config/gworkspace-access/user_token.json"
}

variable "local_config_path" {
  description = "Path to local config.yaml file"
  type        = string
  default     = "../config.yaml"
}

variable "skip_build" {
  description = "Skip Docker build (use existing image)"
  type        = bool
  default     = false
}
