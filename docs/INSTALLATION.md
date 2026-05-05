# Slurm Heartbeat Installation Guide

This guide covers installation and deployment of Slurm Heartbeat on compute clusters for the European Federated Platform (EFP).

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation Methods](#installation-methods)
- [Configuration](#configuration)
- [Running the Daemon](#running-the-daemon)
- [Systemd Service](#systemd-service)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

- **Python**: 3.10 or higher
- **Slurm**: 21.08 or higher (with REST API support)
- **OpenSSL**: 1.1.1+ (for TLS 1.3 support)
- **Operating System**: Linux (tested on Ubuntu 22.04+, RHEL 8+, Debian 11+)

### Slurm REST API

Slurm Heartbeat requires access to the Slurm REST API via `slurmrestd`. Verify your installation:

```bash
# Check slurmrestd availability
which slurmrestd

# Check REST API version
slurmrestd --version

# Test REST API endpoint (requires slurmctld running)
curl -s http://localhost:6820/slurm/v0.0.39/ping
```

### TLS Certificates

For production deployment, you need TLS certificates:

- **Option 1**: Use your site's existing PKI infrastructure
- **Option 2**: Generate self-signed certificates for testing
- **Option 3**: Request certificates from EFP CA (when available)

See [docs/SECURITY.md](SECURITY.md) for certificate requirements.

---

## Installation Methods

### Method 1: Git Clone (Recommended for Development)

```bash
# Clone the repository
git clone https://github.com/saradamian/slurmheartbeat.git
cd slurmheartbeat

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -m slurmheartbeat --help
```

### Method 2: System Package (Production)

For production deployments, consider packaging as a system service:

```bash
# Download and extract release tarball
wget https://github.com/saradamian/slurmheartbeat/releases/download/v1.0.0/slurmheartbeat-1.0.0.tar.gz
tar xzf slurmheartbeat-1.0.0.tar.gz
cd slurmheartbeat-1.0.0

# Install to system location
sudo mkdir -p /opt/slurmheartbeat
sudo cp -r * /opt/slurmheartbeat/

# Create virtual environment
sudo python3 -m venv /opt/slurmheartbeat/venv
sudo /opt/slurmheartbeat/venv/bin/pip install -r /opt/slurmheartbeat/requirements.txt
```

### Method 3: Docker Container

```bash
# Build the image
docker build -t slurmheartbeat:latest .

# Run container
docker run -d \
  --name slurmheartbeat \
  -v /etc/slurm:/etc/slurm:ro \
  -v /var/log/slurmheartbeat:/var/log/slurmheartbeat \
  -p 8443:8443 \
  -p 9090:9090 \
  slurmheartbeat:latest \
  python -m slurmheartbeat --mode both
```

---

## Configuration

### 1. Create Configuration File

```bash
# Create configuration directory
sudo mkdir -p /etc/slurm/heartbeat

# Copy example configuration
sudo cp config.example.yaml /etc/slurm/heartbeat/config.yaml
```

### 2. Edit Configuration

Edit `/etc/slurm/heartbeat/config.yaml` with your site-specific settings:

```yaml
# General settings
general:
  log_level: "INFO"
  log_file: "/var/log/slurmheartbeat/heartbeat.log"

# Client settings (outgoing heartbeats)
client:
  enabled: true
  interval_seconds: 10
  signing_key_file: "/etc/slurm/heartbeat/signing_key.pem"
  federation:
    peers:
      - name: "lumi-prod"
        endpoint: "https://lumi.example.com:8443/readiness"
        peer_public_key_file: "/etc/slurm/heartbeat/peers/lumi.pem"

# Server settings (incoming readiness)
server:
  enabled: true
  listen_port: 8443
  tls:
    enabled: true
    cert_file: "/etc/slurm/heartbeat/server.crt"
    key_file: "/etc/slurm/heartbeat/server.key"
    ca_file: "/etc/slurm/heartbeat/ca.crt"
  allowed_sites:
    - "lumi-prod"
    - "perun-prod"

# Monitoring
monitoring:
  enabled: true
  port: 9090
  path: "/metrics"

# Slurm settings
slurm:
  rest_url: "http://localhost:6820"
  timeout_seconds: 5

# Maintenance mode
maintenance:
  path: "/etc/slurm/heartbeat/maintenance.flag"
```

### 3. Generate TLS Certificates

For testing with self-signed certificates:

```bash
# Generate certificates
./scripts/generate_certs.sh test /etc/slurm/heartbeat

# Set permissions
sudo chmod 600 /etc/slurm/heartbeat/server.key
sudo chmod 644 /etc/slurm/heartbeat/server.crt
sudo chmod 644 /etc/slurm/heartbeat/ca.crt
```

For production, replace with your site's PKI certificates.

### 4. Generate Signing Key

```bash
# Generate RSA signing key (4096-bit)
openssl genrsa -out /etc/slurm/heartbeat/signing_key.pem 4096

# Set permissions
sudo chmod 600 /etc/slurm/heartbeat/signing_key.pem
```

---

## Running the Daemon

### Development Mode

```bash
# Activate virtual environment
source /opt/slurmheartbeat/venv/bin/activate

# Run with verbose logging
python -m slurmheartbeat --config /etc/slurm/heartbeat/config.yaml --verbose

# Run in publisher mode only
python -m slurmheartbeat --mode publisher

# Run in client mode only
python -m slurmheartbeat --mode client

# Run in both modes (default)
python -m slurmheartbeat --mode both
```

### Production Mode (Systemd)

See [Systemd Service](#systemd-service) below.

---

## Systemd Service

### 1. Install Service File

```bash
# Copy service file
sudo cp systemd/slurm-heartbeat.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload
```

### 2. Configure Service

Edit `/etc/systemd/system/slurm-heartbeat.service`:

```ini
[Unit]
Description=Slurm Heartbeat Daemon for EFP
After=network.target slurmctld.service
Wants=slurmctld.service

[Service]
Type=simple
User=root
Group=root
Environment=PATH=/opt/slurmheartbeat/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/opt/slurmheartbeat/venv/bin/python -m slurmheartbeat --config /etc/slurm/heartbeat/config.yaml
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 3. Enable and Start Service

```bash
# Enable service (start on boot)
sudo systemctl enable slurm-heartbeat

# Start service
sudo systemctl start slurm-heartbeat

# Check status
sudo systemctl status slurm-heartbeat

# View logs
sudo journalctl -u slurm-heartbeat -f
```

---

## Verification

### 1. Check Service Status

```bash
# Service is running
sudo systemctl status slurm-heartbeat

# Check for errors in logs
sudo journalctl -u slurm-heartbeat -n 50 --no-pager
```

### 2. Test Endpoints

```bash
# Health endpoint (no auth required)
curl http://localhost:8443/health

# Metrics endpoint (no auth required)
curl http://localhost:9090/metrics

# Readiness endpoint (requires mTLS)
curl --cert client.crt --key client.key --cacert ca.crt \
  https://localhost:8443/readiness
```

### 3. Verify Configuration

```bash
# Validate configuration file
python -m slurmheartbeat --config /etc/slurm/heartbeat/config.yaml --validate

# Check Slurm connectivity
python -m slurmheartbeat --config /etc/slurm/heartbeat/config.yaml --test-connection
```

### 4. Run Tests

```bash
# Run unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=slurmheartbeat --cov-report=html
```

---

## Troubleshooting

### Common Issues

#### 1. "slurmrestd not found"

**Symptom**: Error message "slurmrestd not found" or "Slurm REST API unavailable"

**Solution**:
```bash
# Install Slurm REST API support
sudo apt install slurm-wlm-rest  # Ubuntu/Debian
sudo yum install slurm-rest      # RHEL/CentOS

# Or verify Slurm is compiled with REST support
slurmrestd --version
```

#### 2. TLS Certificate Errors

**Symptom**: "SSL: CERTIFICATE_VERIFY_FAILED" or "certificate verify failed"

**Solution**:
```bash
# Verify certificate paths in config
cat /etc/slurm/heartbeat/config.yaml | grep cert

# Check certificate validity
openssl x509 -in /etc/slurm/heartbeat/server.crt -noout -dates

# Verify certificate chain
openssl verify -CAfile /etc/slurm/heartbeat/ca.crt /etc/slurm/heartbeat/server.crt
```

#### 3. Port Already in Use

**Symptom**: "Address already in use" error

**Solution**:
```bash
# Check what's using the port
sudo lsof -i :8443
sudo lsof -i :9090

# Kill conflicting process or change port in config
```

#### 4. Permission Denied

**Symptom**: "Permission denied" when accessing Slurm REST API

**Solution**:
```bash
# Check Slurm REST API permissions
ls -la /var/run/slurm/

# Run as appropriate user (usually root or slurm)
sudo usermod -aG slurm heartbeat-user
```

#### 5. Signing Key Errors

**Symptom**: "Invalid signing key" or "PEM decoding failed"

**Solution**:
```bash
# Verify key format
openssl rsa -in /etc/slurm/heartbeat/signing_key.pem -check

# Regenerate if needed
openssl genrsa -out /etc/slurm/heartbeat/signing_key.pem 4096
```

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Run with debug logging
python -m slurmheartbeat --config /etc/slurm/heartbeat/config.yaml --verbose

# Or set environment variable
export SLURM_HEARTBEAT_LOG_LEVEL=DEBUG
python -m slurmheartbeat --config /etc/slurm/heartbeat/config.yaml
```

### Logs

Logs are written to:
- **Systemd**: `journalctl -u slurm-heartbeat`
- **File**: `/var/log/slurmheartbeat/heartbeat.log` (if configured)

---

## Next Steps

After installation:

1. **Configure Federation Peers**: Add peer sites to `federation.peers` in config
2. **Set Up Monitoring**: Configure Prometheus to scrape `/metrics`
3. **Test Readiness**: Verify `/readiness` endpoint returns valid signed documents
4. **Review Security**: Ensure certificates are properly secured and rotated

See additional documentation:
- [docs/SECURITY.md](SECURITY.md) - Security and authentication
- [docs/DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment guide
- [docs/OPERATIONS.md](OPERATIONS.md) - Operations and maintenance
- [docs/TESTING.md](TESTING.md) - Testing procedures
- [docs/ADR.md](ADR.md) - Architecture decisions
- [EFP_HEARTBEAT_RECOMMENDATION.md](../EFP_HEARTBEAT_RECOMMENDATION.md) - EFP requirements

---

## Support

- **Project Issues**: [GitHub Issues](https://github.com/saradamian/slurmheartbeat/issues)
- **Documentation**: [docs/](docs/)
- **License**: Apache License 2.0
