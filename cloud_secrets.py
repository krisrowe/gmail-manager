#!/usr/bin/env python3
"""
Cloud Secrets Manager integration for running in Cloud Run.

Detects Cloud Run environment via K_SERVICE env var.
Syncs user_token.json between Secrets Manager and local filesystem.
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Cloud Run Services set K_SERVICE, Jobs set CLOUD_RUN_JOB
def is_cloud_run() -> bool:
    """Detect if running in Cloud Run environment (Service or Job)."""
    return os.environ.get('K_SERVICE') is not None or os.environ.get('CLOUD_RUN_JOB') is not None


def get_secret_name(secret_id: str) -> str:
    """Build full secret resource name."""
    project_id = os.environ.get('GCP_PROJECT_ID')
    if not project_id:
        raise ValueError("GCP_PROJECT_ID env var required for Secrets Manager")
    return f"projects/{project_id}/secrets/{secret_id}/versions/latest"


def download_secret_to_file(secret_id: str, file_path: str) -> bool:
    """
    Download a secret from Secrets Manager and write to local file.

    Args:
        secret_id: The secret ID in Secrets Manager
        file_path: Local path to write the secret content

    Returns:
        True if successful, False otherwise
    """
    try:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        name = get_secret_name(secret_id)

        response = client.access_secret_version(request={"name": name})
        secret_data = response.payload.data.decode("UTF-8")

        # Ensure directory exists
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w') as f:
            f.write(secret_data)

        logger.info(f"Downloaded secret '{secret_id}' to {file_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to download secret '{secret_id}': {e}")
        return False


def upload_file_to_secret(file_path: str, secret_id: str) -> bool:
    """
    Upload a local file's content as a new version of a secret.

    Args:
        file_path: Local path to read content from
        secret_id: The secret ID in Secrets Manager

    Returns:
        True if successful, False otherwise
    """
    try:
        from google.cloud import secretmanager

        with open(file_path, 'r') as f:
            secret_data = f.read()

        client = secretmanager.SecretManagerServiceClient()
        project_id = os.environ.get('GCP_PROJECT_ID')
        parent = f"projects/{project_id}/secrets/{secret_id}"

        response = client.add_secret_version(
            request={
                "parent": parent,
                "payload": {"data": secret_data.encode("UTF-8")}
            }
        )

        logger.info(f"Uploaded {file_path} to secret '{secret_id}' (version: {response.name})")
        return True

    except Exception as e:
        logger.error(f"Failed to upload to secret '{secret_id}': {e}")
        return False


def get_file_hash(file_path: str) -> str:
    """Get MD5 hash of file content for change detection."""
    import hashlib
    try:
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return ""


class CloudSecretsManager:
    """
    Context manager for syncing secrets in Cloud Run.

    Usage:
        with CloudSecretsManager() as csm:
            # token and config files are available locally
            run_gmail_manager()
        # token is synced back to Secrets Manager if changed
    """

    TOKEN_SECRET_ID = "gmail-manager-user-token"
    CONFIG_SECRET_ID = "gmail-manager-config"

    # gwsa token location
    GWSA_CONFIG_DIR = os.path.expanduser("~/.config/gworkspace-access")
    TOKEN_FILE = os.path.join(GWSA_CONFIG_DIR, "user_token.json")

    # config.yaml location (same directory as the script)
    CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")

    def __init__(self):
        self.is_cloud = is_cloud_run()
        self.token_hash_before = None

    def __enter__(self):
        if not self.is_cloud:
            logger.info("Local environment detected, using local files")
            return self

        logger.info("Cloud Run detected, downloading secrets from Secrets Manager")

        # Download token
        if download_secret_to_file(self.TOKEN_SECRET_ID, self.TOKEN_FILE):
            self.token_hash_before = get_file_hash(self.TOKEN_FILE)
        else:
            raise RuntimeError("Failed to download user token from Secrets Manager")

        # Download config
        if not download_secret_to_file(self.CONFIG_SECRET_ID, self.CONFIG_FILE):
            raise RuntimeError("Failed to download config from Secrets Manager")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.is_cloud:
            return False

        # Check if token changed (was refreshed)
        token_hash_after = get_file_hash(self.TOKEN_FILE)

        if token_hash_after and token_hash_after != self.token_hash_before:
            logger.info("Token was refreshed, uploading to Secrets Manager")
            upload_file_to_secret(self.TOKEN_FILE, self.TOKEN_SECRET_ID)
        else:
            logger.debug("Token unchanged, skipping upload")

        return False  # Don't suppress exceptions
