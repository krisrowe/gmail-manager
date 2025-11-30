# Gmail Manager Deployment Plan

## Cloud Deployment Strategy (GCP Cloud Run)

### Production Environment (Future)
When deployed to production on Google Cloud Run, the application will leverage:

1. **GCP Secrets Manager Integration**
   - Store gwsa credentials (gworkspace-access config) in GCP Secrets Manager
   - Inject secrets as environment variables in Cloud Run service configuration
   - No credentials stored in container images or configuration files

2. **Environment Variable Configuration**
   - Leverage existing `app_config.py` environment variable override pattern
   - Set Cloud Run environment variables:
     - `GMAIL_MANAGER_CONFIG_DIR`: Path to mounted secrets/config volume (e.g., `/var/secrets/config`)
     - `GMAIL_MANAGER_DATA_DIR`: Path to mounted persistent storage volume (e.g., `/var/data/gmail-manager`)
     - `GWSA_CONFIG_DIR`: Path to gworkspace-access secrets (e.g., `/var/secrets/gwsa`)

3. **Volume Mounts**
   - Mount GCP Secret Manager secrets to `/var/secrets/config` and `/var/secrets/gwsa`
   - Mount Cloud Storage bucket or persistent disk to `/var/data/gmail-manager` for:
     - `processed_*.json` files (audit trail)
     - `rules_usage.json` (tracking)
     - Logs (if implemented)

4. **Container Runtime**
   - Application code runs in containerized environment
   - All dynamic state written to persistent volumes
   - No local filesystem dependencies on container ephemeral storage

### Current Development Pattern
The application already follows the pattern needed for cloud deployment:
- `app_config.py` centralizes all path configuration
- Environment variable overrides allow deployment flexibility
- Auto-creates directories on startup (no manual setup required)
- All file operations use configurable paths (not hardcoded)
- Stateless application design (credentials external, state in configurable paths)

### Implementation Readiness
✓ Architecture already supports environment-based configuration
✓ No hardcoded paths in application code
✓ Path management centralized in `app_config.py`
✓ All utilities (rules_usage.py, report.py, convert_processed_dates.py) now import app_config
✓ Ready for containerization and cloud deployment

### Minimal Changes for Cloud Deployment
When deploying to Cloud Run:
1. Set environment variables in Cloud Run service configuration
2. Mount volumes as specified in Cloud Run deployment YAML
3. Application will automatically use configured paths
4. No code changes required
