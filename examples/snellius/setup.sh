#!/bin/bash
# Automated setup script for Slurm Heartbeat on Snellius (SURF)
# Run this after cloning the repository and creating a virtual environment

set -e

echo "=== Slurm Heartbeat Setup for Snellius ==="
echo ""

# Check if running on Snellius
if [[ -z "$HPC_ENV" ]] && [[ -z "$SNELLIUS" ]]; then
    echo "Warning: Not detected on Snellius. Proceeding anyway..."
fi

# Check if virtual environment is active
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "Error: No virtual environment active. Please run:"
    echo "  module load 2025"
    echo "  module load Python/3.11.6"
    echo "  python -m venv venv"
    echo "  source venv/bin/activate"
    exit 1
fi

echo "✓ Virtual environment detected: $VIRTUAL_ENV"

# Create directories
echo ""
echo "Creating directories..."
mkdir -p "$HOME/.slurm/heartbeat"
mkdir -p "$HOME/logs/slurmheartbeat"
chmod 700 "$HOME/.slurm/heartbeat"
chmod 700 "$HOME/logs/slurmheartbeat"
echo "✓ Created $HOME/.slurm/heartbeat"
echo "✓ Created $HOME/logs/slurmheartbeat"

# Copy configuration
echo ""
echo "Copying configuration..."
if [[ -f "examples/snellius/config.yaml" ]]; then
    cp examples/snellius/config.yaml "$HOME/.slurm/heartbeat/config.yaml"
    echo "✓ Copied config.yaml to $HOME/.slurm/heartbeat/"
else
    echo "Warning: examples/snellius/config.yaml not found"
    echo "Creating default config..."
    cat > "$HOME/.slurm/heartbeat/config.yaml" << 'EOF'
general:
  log_level: "INFO"
  log_file: "$HOME/logs/slurmheartbeat/heartbeat.log"

cluster:
  id: "snellius"
  name: "snellius-surfnl"
  site: "SURF Netherlands"

client:
  enabled: true
  interval_seconds: 10
  slurm:
    api_url: "http://localhost:6820"
    api_version: "0.0.39"
  tls:
    enabled: true
    cert_file: "$HOME/.slurm/heartbeat/server.crt"
    key_file: "$HOME/.slurm/heartbeat/server.key"
    ca_file: "$HOME/.slurm/heartbeat/ca.crt"
    signing_key_file: "$HOME/.slurm/heartbeat/signing_key.pem"
  federation:
    peers: []

server:
  enabled: true
  listen_address: "127.0.0.1"
  listen_port: 8443
  allowed_sites:
    - "snellius"
  tls:
    enabled: true
    cert_file: "$HOME/.slurm/heartbeat/server.crt"
    key_file: "$HOME/.slurm/heartbeat/server.key"
    ca_file: "$HOME/.slurm/heartbeat/ca.crt"
    client_auth: "optional"
  peer_public_keys: {}
  signing_key_file: "$HOME/.slurm/heartbeat/signing_key.pem"

monitoring:
  enabled: true
  port: 9090
  path: "/metrics"
  listen_address: "127.0.0.1"

slurm:
  rest_url: "http://localhost:6820"
  timeout_seconds: 5

maintenance:
  path: "$HOME/.slurm/heartbeat/maintenance.flag"
EOF
fi

# Generate signing key
echo ""
echo "Generating signing key..."
if [[ ! -f "$HOME/.slurm/heartbeat/signing_key.pem" ]]; then
    openssl genrsa -out "$HOME/.slurm/heartbeat/signing_key.pem" 4096
    chmod 600 "$HOME/.slurm/heartbeat/signing_key.pem"
    echo "✓ Generated signing_key.pem"
else
    echo "✓ signing_key.pem already exists"
fi

# Generate TLS certificates (self-signed for testing)
echo ""
echo "Generating TLS certificates (self-signed for testing)..."
if [[ ! -f "$HOME/.slurm/heartbeat/server.crt" ]] || [[ ! -f "$HOME/.slurm/heartbeat/server.key" ]]; then
    # Generate CA
    openssl genrsa -out "$HOME/.slurm/heartbeat/ca.key" 4096
    openssl req -x509 -new -nodes -key "$HOME/.slurm/heartbeat/ca.key" \
        -sha256 -days 365 -out "$HOME/.slurm/heartbeat/ca.crt" \
        -subj "/C=NL/O=SURF/OU=Snellius/CN=snellius-surfnl"
    
    # Generate server key
    openssl genrsa -out "$HOME/.slurm/heartbeat/server.key" 4096
    
    # Generate CSR
    openssl req -new -key "$HOME/.slurm/heartbeat/server.key" \
        -out "$HOME/.slurm/heartbeat/server.csr" \
        -subj "/C=NL/O=SURF/OU=Snellius/CN=snellius-surfnl"
    
    # Sign server certificate
    openssl x509 -req -in "$HOME/.slurm/heartbeat/server.csr" \
        -CA "$HOME/.slurm/heartbeat/ca.crt" -CAkey "$HOME/.slurm/heartbeat/ca.key" \
        -CAcreateserial -out "$HOME/.slurm/heartbeat/server.crt" \
        -days 365 -sha256
    
    chmod 600 "$HOME/.slurm/heartbeat/server.key"
    chmod 644 "$HOME/.slurm/heartbeat/server.crt"
    chmod 644 "$HOME/.slurm/heartbeat/ca.crt"
    chmod 600 "$HOME/.slurm/heartbeat/ca.key"
    
    echo "✓ Generated server.crt, server.key, ca.crt, ca.key"
else
    echo "✓ TLS certificates already exist"
fi

# Verify Slurm REST API
echo ""
echo "Verifying Slurm REST API..."
if curl -s --max-time 5 http://localhost:6820/slurm/v0.0.39/ping > /dev/null 2>&1; then
    echo "✓ Slurm REST API is accessible"
else
    echo "⚠ Warning: Slurm REST API not accessible at http://localhost:6820"
    echo "  This is expected if you're not on a compute node or if Slurm is not running."
    echo "  The heartbeat daemon will report 'unavailable' status until Slurm is accessible."
fi

# Verify installation
echo ""
echo "Verifying installation..."
if python -m slurmheartbeat --help > /dev/null 2>&1; then
    echo "✓ Slurm Heartbeat is installed and runnable"
else
    echo "✗ Error: Slurm Heartbeat not found. Please run:"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Summary
echo ""
echo "=== Setup Complete ==="
echo ""
echo "Configuration files:"
echo "  - Config: $HOME/.slurm/heartbeat/config.yaml"
echo "  - Signing key: $HOME/.slurm/heartbeat/signing_key.pem"
echo "  - TLS cert: $HOME/.slurm/heartbeat/server.crt"
echo "  - TLS key: $HOME/.slurm/heartbeat/server.key"
echo "  - CA cert: $HOME/.slurm/heartbeat/ca.crt"
echo ""
echo "To run Slurm Heartbeat:"
echo "  # Option A: Screen session (recommended)"
echo "  screen -S slurmheartbeat"
echo "  source $VIRTUAL_ENV/bin/activate"
echo "  python -m slurmheartbeat --config $HOME/.slurm/heartbeat/config.yaml"
echo "  # Detach: Ctrl+A, then D"
echo ""
echo "  # Option B: Background process"
echo "  nohup $VIRTUAL_ENV/bin/python -m slurmheartbeat \\"
echo "    --config $HOME/.slurm/heartbeat/config.yaml \\"
echo "    > $HOME/logs/slurmheartbeat/nohup.out 2>&1 &"
echo ""
echo "  # Option C: Slurm job (testing only)"
echo "  sbatch examples/snellius/run_heartbeat.slurm"
echo ""
echo "For more information, see examples/snellius/README.md"
