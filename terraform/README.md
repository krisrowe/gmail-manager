# Terraform Deployment

Deploys gmail-manager to Cloud Run Jobs with scheduled execution.

## Prerequisites

1. GCP project with billing enabled and labeled `gws-access:default`
2. `gcloud` CLI authenticated
3. `gwsa` configured locally with valid `user_token.json`
4. Terraform installed

## Setup

Set your project ID (used in all commands below):

```bash
PROJECT_ID=$(gcloud projects list --filter="labels.gws-access=default" --format="value(projectId)")
```

## Deploy

```bash
cd terraform
terraform init
terraform apply -var="project_id=$PROJECT_ID"
```

### Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `project_id` | GCP project ID (required) | - |
| `region` | GCP region | `us-central1` |
| `schedule` | Cron schedule | `0 */6 * * *` (every 6 hours) |
| `skip_build` | Skip Docker build | `false` |

### Skip Docker Build

Apply without rebuilding the image:

```bash
terraform apply -var="project_id=$PROJECT_ID" -var="skip_build=true"
```

## What Gets Created

- Required GCP APIs (Cloud Run, Scheduler, Secret Manager, Artifact Registry, Cloud Build)
- Service account (`gmail-manager-runner`) with Secret Manager access
- Secrets (user_token.json, config.yaml from local files)
- Artifact Registry repository
- Cloud Run Job
- Cloud Scheduler (triggers every 6 hours)

## Manual Execution

### Local

Run on your machine with local credentials (see main [README.md](../README.md)):

```bash
python gmail_manager.py
```

### Cloud

Trigger the deployed job:

```bash
gcloud run jobs execute gmail-manager --region=us-central1 --project=$PROJECT_ID
```

View logs:

```bash
# Application output only
gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="gmail-manager" AND textPayload:*' \
  --project=$PROJECT_ID --limit=50 --format="value(textPayload)"

# Full log details
gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="gmail-manager"' \
  --project=$PROJECT_ID --limit=20
```

## Scheduler

```bash
# Status
gcloud scheduler jobs describe gmail-manager-trigger --location=us-central1 --project=$PROJECT_ID

# Pause
gcloud scheduler jobs pause gmail-manager-trigger --location=us-central1 --project=$PROJECT_ID

# Resume
gcloud scheduler jobs resume gmail-manager-trigger --location=us-central1 --project=$PROJECT_ID

# Trigger now
gcloud scheduler jobs run gmail-manager-trigger --location=us-central1 --project=$PROJECT_ID
```

## State File

State is stored locally in `terraform.tfstate` (gitignored). If lost, import resources:

```bash
terraform import google_service_account.gmail_manager \
  projects/$PROJECT_ID/serviceAccounts/gmail-manager-runner@$PROJECT_ID.iam.gserviceaccount.com
```
