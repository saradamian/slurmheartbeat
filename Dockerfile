# Use Python 3.10 slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash heartbeat && \
    chown -R heartbeat:heartbeat /app
USER heartbeat

# Create directories for runtime
RUN mkdir -p /var/log/slurm-heartbeat /etc/slurm/heartbeat

# Expose ports
EXPOSE 8443  # Readiness endpoint (HTTPS)
EXPOSE 9090  # Metrics endpoint (HTTP)

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f -k https://localhost:8443/health || exit 1

# Default command
CMD ["python", "-m", "slurmheartbeat"]
