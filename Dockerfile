FROM python:3.11

WORKDIR /app

# Copy project files (config.yaml downloaded from Secrets Manager at runtime)
COPY pyproject.toml ./
COPY *.py ./

# Install with cloud extras (includes gwsa-cli and google-cloud-secret-manager)
RUN pip install --no-cache-dir ".[cloud]"

# Create gwsa config directory
RUN mkdir -p /root/.config/gworkspace-access

# Run the gmail manager
CMD ["python", "gmail_manager.py", "--limit", "500"]
