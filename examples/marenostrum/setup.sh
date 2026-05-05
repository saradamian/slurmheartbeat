#!/bin/bash
# Automated setup script for Slurm Heartbeat on MareNostrum5 (BSC Spain)
# Run this with sudo for production deployment

set -e

echo "=== Slurm Heartbeat Setup for MareNostrum5 ==="
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (sudo)"
    exit 1
fi

# Check if virtual environment exists
if [[ ! -d "/opt/slurmheartbeat/venv" ]]; then
    echo "Error: Virtual environment not found at /opt/slurmheartbeat/venv"
    echo "Please run:"
    echo "  sudo python3 -m venv /opt/slurmheartbeat/venv"
    echo "  sudo /opt/slurmheartbeat/venv/bin/pip install -r requirements.txt"
    exit 1
fi

echo "✓ Virtual environment found: /opt/slurmheartbeat/venv"

# Create directories
echo ""
echo "Creating directories..."
mkdir -p /etc/slurm/heartbeat
mkdir -p /var/log/slurm
mkdir -p /var/run/slurmheartbeat
chmod 700 /etc/slurm/heartbeat
chmod 755 /var/log/slurm
chmod 700 /var/run/slurmheartbeat
echo "✓ Created /etc/slurm/heartbeat"
echo "✓ Created /var/log/slurm"
echo "✓ Created /var/run/slurmheartbeat"

# Copy configuration
echo ""
echo "Copying configuration..."
if [[ -f "examples/marenostrum/config.yaml" ]]; then
    cp examples/marenostrum/config.yaml /etc/slurm/heartbeat/config.yaml
    echo "✓ Copied config.yaml to /etc/slurm/heartbeat/"
else
    echo "Warning: examples/marenostrum/config.yaml not found"
    echo "Creating default config..."
    cat > /etc/slurm/heartbeat/config.yaml << 'EOF'
general:
  log_level: "INFO"
  log_file: "/var/log/slurm/heartbeat.log"

cluster:
  id: "marenostrum5"
  name: "marenostrum5-bsc-es"
  site: "BSC Spain"

client:
  enabled: true
  interval_seconds: 10
  slurm:
    api_url: "http://localhost:6820"
    api_version: "0.0.39"
  tls:
    enabled: true
    cert_file: "/etc/slurm/heartbeat/server.crt"
    key_file: "/etc/slurm/heartbeat/server.key"
    ca_file: "/etc/slurm/heartbeat/ca.crt"
    signing_key_file: "/etc/slurm/heartbeat/signing_key.pem"
  federation:
    peers: []

server:
  enabled: true
  listen_address: "0.0.0.0"
  listen_port: 8443
  allowed_sites:
    - "marenostrum5"
  tls:
    enabled: true
    cert_file: "/etc/slurm/heartbeat/server.crt"
    key_file: "/etc/slurm/heartbeat/server.key"
    ca_file: "/etc/slurm/heartbeat/ca.crt"
    client_auth: "required"
  peer_public_keys: {}
  signing_key_file: "/etc/slurm/heartbeat/signing_key.pem"

monitoring:
  enabled: true
  port: 9090
  path: "/metrics"
  listen_address: "0.0.0.0"

slurm:
  rest_url: "http://localhost:6820"
  timeout_seconds: 5

maintenance:
  path: "/var/run/slurmheartbeat/maintenance.flag"
EOF
fi

# Generate signing key
echo ""
echo "Generating signing key..."
if [[ ! -f "/etc/slurm/heartbeat/signing_key.pem" ]]; then
    openssl genrsa -out /etc/slurm/heartbeat/signing_key.pem 4096
    chmod 600 /etc/slurm/heartbeat/signing_key.pem
    echo "✓ Generated signing_key.pem"
else
    echo "✓ signing_key.pem already exists"
fi

# Generate TLS certificates (self-signed for testing)
echo ""
echo "Generating TLS certificates (self-signed for testing)..."
if [[ ! -f "/etc/slurm/heartbeat/server.crt" ]] || [[ ! -f "/etc/slurm/heartbeat/server.key" ]]; then
    # Generate CA
    openssl genrsa -out /etc/slurm/heartbeat/ca.key 4096
    openssl req -x509 -new -nodes -key /etc/slurm/heartbeat/ca.key \
        -sha256 -days 365 -out /etc/slurm/heartbeat/ca.crt \
        -subj "/C=ES/O=BSC/OU=MareNostrum5/CN=marenostrum5-bsc-es"
    
    # Generate server key
    openssl genrsa -out /etc/slurm/heartbeat/server.key 4096
    
    # Generate CSR
    openssl req -new -key /etc/slurm/heartbeat/server.key \
        -out /etc/slurm/heartbeat/server.csr \
        -subj "/C=ES/O=BSC/OU=MareNostrum5/CN=marenostrum5-bsc-es"
    
    # Sign server certificate
    openssl x509 -req -in /etc/slurm/heartbeat/server.csr \
        -CA /etc/slurm/heartbeat/ca.crt -CAkey /etc/slurm/heartbeat/ca.key \
        -CAcreateserial -out /etc/slurm/heartbeat/server.crt \
        -days 365 -sha256
    
    chmod 600 /etc/slurm/heartbeat/server.key
    chmod 644 /etc/slurm/heartbeat/server.crt
    chmod 644 /etc/slurm/heartbeat/ca.crt
    
    echo "✓ Generated self-signed certificates"
    echo "  Note: For production, use BSC PKI or EFP CA certificates"
else
    echo "✓ TLS certificates already exist"
fi

# Install systemd service
echo ""
echo "Installing systemd service..."
if [[ -f "systemd/slurm-heartbeat.service" ]]; then
    cp systemd/slurm-heartbeat.service /etc/systemd/system/
    systemctl daemon-reload
    echo "✓ Installed systemd service"
else
    echo "Warning: systemd/slurm-heartbeat.service not found"
    echo "Manual installation required"
fi

# Enable and start service
echo ""
echo "Enabling and starting service..."
systemctl enable slurm-heartbeat
systemctl start slurm-heartbeat
echo "✓ Service enabled and started"

# Summary
echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Review configuration: /etc/slurm/heartbeat/config.yaml"
echo "2. Check service status: systemctl status slurm-heartbeat"
echo "3. View logs: journalctl -u slurm-heartbeat -f"
echo "4. Verify endpoints:"
echo "   - Health: curl -k https://localhost:8443/health"
echo "   - Metrics: curl http://localhost:9090/metrics"
echo "   - Readiness: curl --cert cert.pem --key key.pem --cacert ca.pem https://localhost:8443/readiness"
echo ""
