#!/bin/bash
# Verification script for Slurm Heartbeat on DAEDALUS
set -e

echo "=== Slurm Heartbeat Verification for DAEDALUS ==="

python --version
echo "✓ Python version OK"

if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "✗ No virtual environment active"
    exit 1
else
    echo "✓ Virtual environment: $VIRTUAL_ENV"
fi

$VIRTUAL_ENV/bin/python -c "import yaml; import requests; import cryptography; import prometheus_client" && \
    echo "✓ All dependencies installed" || \
    echo "✗ Missing dependencies"

CONFIG_FILE="$HOME/.slurm/heartbeat/config.yaml"
if [[ -f "$CONFIG_FILE" ]]; then
    echo "✓ Config file exists"
    $VIRTUAL_ENV/bin/python -c "import yaml; yaml.safe_load(open('$CONFIG_FILE'))" && \
        echo "✓ Config file is valid YAML" || \
        echo "✗ Invalid YAML"
else
    echo "✗ Config file not found"
fi

CERT_DIR="$HOME/.slurm/heartbeat"
[[ -f "$CERT_DIR/signing_key.pem" ]] && echo "✓ Signing key exists" || echo "✗ Signing key not found"
[[ -f "$CERT_DIR/server.crt" ]] && [[ -f "$CERT_DIR/server.key" ]] && echo "✓ TLS certificates exist" || echo "✗ TLS certificates not found"
[[ -f "$CERT_DIR/ca.crt" ]] && echo "✓ CA certificate exists" || echo "✗ CA certificate not found"

if curl -s --max-time 5 http://localhost:6820/slurm/v0.0.39/ping > /dev/null 2>&1; then
    echo "✓ Slurm REST API is accessible"
else
    echo "⚠ Slurm REST API not accessible"
fi

$VIRTUAL_ENV/bin/python -m slurmheartbeat --help > /dev/null 2>&1 && \
    echo "✓ Module is executable" || \
    echo "✗ Module execution failed"

echo "=== Verification Complete ==="
