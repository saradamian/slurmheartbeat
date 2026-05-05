#!/bin/bash
# Automated setup script for Slurm Heartbeat on Leonardo (CRESCO Italy)
set -e

echo "=== Slurm Heartbeat Setup for Leonardo ==="

if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (sudo)"
    exit 1
fi

if [[ ! -d "/opt/slurmheartbeat/venv" ]]; then
    echo "Error: Virtual environment not found"
    exit 1
fi

echo "✓ Virtual environment found"

# Create directories
mkdir -p /etc/slurm/heartbeat /var/log/slurm /var/run/slurmheartbeat
chmod 700 /etc/slurm/heartbeat

# Copy configuration
if [[ -f "examples/leonardo/config.yaml" ]]; then
    cp examples/leonardo/config.yaml /etc/slurm/heartbeat/config.yaml
    echo "✓ Copied config.yaml"
fi

# Generate signing key
if [[ ! -f "/etc/slurm/heartbeat/signing_key.pem" ]]; then
    openssl genrsa -out /etc/slurm/heartbeat/signing_key.pem 4096
    chmod 600 /etc/slurm/heartbeat/signing_key.pem
    echo "✓ Generated signing key"
fi

# Generate TLS certificates
if [[ ! -f "/etc/slurm/heartbeat/server.crt" ]]; then
    openssl genrsa -out /etc/slurm/heartbeat/ca.key 4096
    openssl req -x509 -new -nodes -key /etc/slurm/heartbeat/ca.key \
        -sha256 -days 365 -out /etc/slurm/heartbeat/ca.crt \
        -subj "/C=IT/O=CRESCO/OU=Leonardo/CN=leonardo-creSCO-it"
    openssl genrsa -out /etc/slurm/heartbeat/server.key 4096
    openssl req -new -key /etc/slurm/heartbeat/server.key \
        -out /etc/slurm/heartbeat/server.csr \
        -subj "/C=IT/O=CRESCO/OU=Leonardo/CN=leonardo-creSCO-it"
    openssl x509 -req -in /etc/slurm/heartbeat/server.csr \
        -CA /etc/slurm/heartbeat/ca.crt -CAkey /etc/slurm/heartbeat/ca.key \
        -CAcreateserial -out /etc/slurm/heartbeat/server.crt \
        -days 365 -sha256
    chmod 600 /etc/slurm/heartbeat/server.key
    chmod 644 /etc/slurm/heartbeat/server.crt
    chmod 644 /etc/slurm/heartbeat/ca.crt
    echo "✓ Generated TLS certificates"
fi

# Install systemd service
if [[ -f "systemd/slurm-heartbeat.service" ]]; then
    cp systemd/slurm-heartbeat.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable slurm-heartbeat
    systemctl start slurm-heartbeat
    echo "✓ Service installed and started"
fi

echo "=== Setup Complete ==="
