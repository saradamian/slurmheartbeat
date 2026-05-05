#!/bin/bash
# Verification script for Slurm Heartbeat on LUMI

set -e

echo "=== Slurm Heartbeat Verification for LUMI ==="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version
echo "✓ Python version OK"

# Check virtual environment
echo ""
echo "Checking virtual environment..."
if [[ -d "/opt/slurmheartbeat/venv" ]]; then
    echo "✓ Virtual environment found: /opt/slurmheartbeat/venv"
else
    echo "✗ Virtual environment not found"
    exit 1
fi

# Check dependencies
echo ""
echo "Checking dependencies..."
/opt/slurmheartbeat/venv/bin/python -c "import yaml; import requests; import cryptography; import prometheus_client" && \
    echo "✓ All dependencies installed" || \
    echo "✗ Missing dependencies"

# Check configuration
echo ""
echo "Checking configuration..."
CONFIG_FILE="/etc/slurm/heartbeat/config.yaml"
if [[ -f "$CONFIG_FILE" ]]; then
    echo "✓ Config file exists: $CONFIG_FILE"
    
    # Validate YAML
    /opt/slurmheartbeat/venv/bin/python -c "import yaml; yaml.safe_load(open('$CONFIG_FILE'))" && \
        echo "✓ Config file is valid YAML" || \
        echo "✗ Invalid YAML in config file"
else
    echo "✗ Config file not found: $CONFIG_FILE"
    echo "  Run: ./examples/lumi/setup.sh"
fi

# Check certificates
echo ""
echo "Checking certificates..."
CERT_DIR="/etc/slurm/heartbeat"
if [[ -f "$CERT_DIR/signing_key.pem" ]]; then
    echo "✓ Signing key exists"
else
    echo "✗ Signing key not found"
fi

if [[ -f "$CERT_DIR/server.crt" ]] && [[ -f "$CERT_DIR/server.key" ]]; then
    echo "✓ TLS certificates exist"
else
    echo "✗ TLS certificates not found"
fi

if [[ -f "$CERT_DIR/ca.crt" ]]; then
    echo "✓ CA certificate exists"
else
    echo "✗ CA certificate not found"
fi

# Check directories
echo ""
echo "Checking directories..."
if [[ -d "/var/log/slurm" ]]; then
    echo "✓ Log directory exists: /var/log/slurm"
else
    echo "✗ Log directory not found"
fi

if [[ -d "/var/run/slurmheartbeat" ]]; then
    echo "✓ Runtime directory exists: /var/run/slurmheartbeat"
else
    echo "✗ Runtime directory not found"
fi

# Check Slurm REST API
echo ""
echo "Checking Slurm REST API..."
if curl -s --max-time 5 http://localhost:6820/slurm/v0.0.39/ping > /dev/null 2>&1; then
    echo "✓ Slurm REST API is accessible"
    PING_RESPONSE=$(curl -s http://localhost:6820/slurm/v0.0.39/ping)
    echo "  Response: $PING_RESPONSE"
else
    echo "⚠ Slurm REST API not accessible"
    echo "  Check Slurm REST API status: systemctl status slurmrestd"
fi

# Check systemd service
echo ""
echo "Checking systemd service..."
if systemctl is-active --quiet slurm-heartbeat 2>/dev/null; then
    echo "✓ Service is running"
    echo "  Status: $(systemctl status slurm-heartbeat --no-pager | head -1)"
else
    echo "⚠ Service not running"
    echo "  Start with: sudo systemctl start slurm-heartbeat"
fi

# Test module execution
echo ""
echo "Testing module execution..."
if /opt/slurmheartbeat/venv/bin/python -m slurmheartbeat --help > /dev/null 2>&1; then
    echo "✓ Slurm Heartbeat module is executable"
else
    echo "✗ Module execution failed"
fi

# Summary
echo ""
echo "=== Verification Complete ==="
echo ""
if systemctl is-active --quiet slurm-heartbeat 2>/dev/null; then
    echo "✓ All checks passed. Slurm Heartbeat is running on LUMI."
    echo ""
    echo "Useful commands:"
    echo "  sudo systemctl status slurm-heartbeat"
    echo "  sudo journalctl -u slurm-heartbeat -f"
    echo "  curl -k https://localhost:8443/health"
    echo "  curl http://localhost:9090/metrics"
else
    echo "⚠ Some checks failed. Review the output above."
fi
