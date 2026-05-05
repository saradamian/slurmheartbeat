#!/bin/bash
# Automated setup script for Slurm Heartbeat on DEUCALION (Spain)
set -e

echo "=== Slurm Heartbeat Setup for DEUCALION ==="

if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "Error: No virtual environment active"
    exit 1
fi

echo "✓ Virtual environment detected: $VIRTUAL_ENV"

mkdir -p "$HOME/.slurm/heartbeat"
mkdir -p "$HOME/logs/slurmheartbeat"
chmod 700 "$HOME/.slurm/heartbeat"
chmod 700 "$HOME/logs/slurmheartbeat"
echo "✓ Created directories"

if [[ -f "examples/deucalion/config.yaml" ]]; then
    cp examples/deucalion/config.yaml "$HOME/.slurm/heartbeat/config.yaml"
    echo "✓ Copied config.yaml"
fi

if [[ ! -f "$HOME/.slurm/heartbeat/signing_key.pem" ]]; then
    openssl genrsa -out "$HOME/.slurm/heartbeat/signing_key.pem" 4096
    chmod 600 "$HOME/.slurm/heartbeat/signing_key.pem"
    echo "✓ Generated signing key"
fi

if [[ ! -f "$HOME/.slurm/heartbeat/server.crt" ]]; then
    openssl genrsa -out "$HOME/.slurm/heartbeat/ca.key" 4096
    openssl req -x509 -new -nodes -key "$HOME/.slurm/heartbeat/ca.key" \
        -sha256 -days 365 -out "$HOME/.slurm/heartbeat/ca.crt" \
        -subj "/C=ES/O=DEUCALION/CN=deucalion-es"
    openssl genrsa -out "$HOME/.slurm/heartbeat/server.key" 4096
    openssl req -new -key "$HOME/.slurm/heartbeat/server.key" \
        -out "$HOME/.slurm/heartbeat/server.csr" \
        -subj "/C=ES/O=DEUCALION/CN=deucalion-es"
    openssl x509 -req -in "$HOME/.slurm/heartbeat/server.csr" \
        -CA "$HOME/.slurm/heartbeat/ca.crt" -CAkey "$HOME/.slurm/heartbeat/ca.key" \
        -CAcreateserial -out "$HOME/.slurm/heartbeat/server.crt" \
        -days 365 -sha256
    chmod 600 "$HOME/.slurm/heartbeat/server.key"
    chmod 644 "$HOME/.slurm/heartbeat/server.crt"
    chmod 644 "$HOME/.slurm/heartbeat/ca.crt"
    echo "✓ Generated TLS certificates"
fi

echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Run: screen -S slurmheartbeat"
echo "2. source $VIRTUAL_ENV/bin/activate"
echo "3. python -m slurmheartbeat --config $HOME/.slurm/heartbeat/config.yaml"
