#!/bin/bash
# Verification script for Slurm Heartbeat on Snellius

set -e

echo "=== Slurm Heartbeat Verification for Snellius ==="
echo ""

# Check Python version
echo "Checking Python version..."
python --version
echo "✓ Python version OK"

# Check virtual environment
echo ""
echo "Checking virtual environment..."
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠ Warning: No virtual environment active"
    echo "  Run: source $HOME/slurmheartbeat/venv/bin/activate"
else
    echo "✓ Virtual environment: $VIRTUAL_ENV"
fi

# Check dependencies
echo ""
echo "Checking dependencies..."
python -c "import yaml; import requests; import cryptography; import prometheus_client" && \
    echo "✓ All dependencies installed" || \
    echo "✗ Missing dependencies. Run: pip install -r requirements.txt"

# Check configuration
echo ""
echo "Checking configuration..."
CONFIG_FILE="$HOME/.slurm/heartbeat/config.yaml"
if [[ -f "$CONFIG_FILE" ]]; then
    echo "✓ Config file exists: $CONFIG_FILE"
    
    # Validate YAML
    python -c "import yaml; yaml.safe_load(open('$CONFIG_FILE'))" && \
        echo "✓ Config file is valid YAML" || \
        echo "✗ Invalid YAML in config file"
else
    echo "✗ Config file not found: $CONFIG_FILE"
    echo "  Run: ./examples/snellius/setup.sh"
fi

# Check certificates
echo ""
echo "Checking certificates..."
CERT_DIR="$HOME/.slurm/heartbeat"
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
if [[ -d "$HOME/logs/slurmheartbeat" ]]; then
    echo "✓ Log directory exists: $HOME/logs/slurmheartbeat"
else
    echo "✗ Log directory not found"
fi

# Check Slurm REST API
echo ""
echo "Checking Slurm REST API..."
if curl -s --max-time 5 http://localhost:6820/slurm/v0.0.39/ping > /dev/null 2>&1; then
    echo "✓ Slurm REST API is accessible"
    PING_RESPONSE=$(curl -s http://localhost:6820/slurm/v0.0.39/ping)
    echo "  Response: $PING_RESPONSE"
else
    echo "⚠ Slurm REST API not accessible (expected on login nodes)"
    echo "  The daemon will report 'unavailable' status until Slurm is accessible"
fi

# Test module execution
echo ""
echo "Testing module execution..."
if python -m slurmheartbeat --help > /dev/null 2>&1; then
    echo "✓ Slurm Heartbeat module is executable"
else
    echo "✗ Module execution failed"
fi

# Summary
echo ""
echo "=== Verification Complete ==="
echo ""
echo "If all checks passed, you can start Slurm Heartbeat:"
echo ""
echo "  # Option A: Screen session (recommended)"
echo "  screen -S slurmheartbeat"
echo "  source $VIRTUAL_ENV/bin/activate"
echo "  python -m slurmheartbeat --config $HOME/.slurm/heartbeat/config.yaml"
echo ""
echo "  # Option B: Background process"
echo "  nohup $VIRTUAL_ENV/bin/python -m slurmheartbeat \\"
echo "    --config $HOME/.slurm/heartbeat/config.yaml \\"
echo "    > $HOME/logs/slurmheartbeat/nohup.out 2>&1 &"
echo ""
echo "  # Option C: Slurm job (testing only)"
echo "  sbatch examples/snellius/run_heartbeat.slurm"
