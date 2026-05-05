# Slurm Heartbeat on MareNostrum5 (BSC Spain)

This directory contains configuration and scripts for running Slurm Heartbeat on the MareNostrum5 supercomputer operated by the Barcelona Supercomputing Center (BSC).

## Overview

MareNostrum5 is one of Europe's most powerful supercomputers, operated by the Barcelona Supercomputing Center (BSC) in Spain. This guide covers **production deployment** using systemd services.

## Key Differences from Standard Deployment

| Component | Standard (systemd) | MareNostrum5 (production) |
|-----------|-------------------|---------------------------|
| **Installation** | `/opt/slurmheartbeat/` | `/opt/slurmheartbeat/` |
| **Python env** | System venv | System venv |
| **Service** | `systemctl start` | `systemctl start` |
| **Config** | `/etc/slurm/heartbeat/` | `/etc/slurm/heartbeat/` |
| **Logs** | `/var/log/slurm/` | `/var/log/slurm/` |
| **Certificates** | `/etc/slurm/heartbeat/` | `/etc/slurm/heartbeat/` |

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
sudo python3 -m venv /opt/slurmheartbeat/venv
sudo /opt/slurmheartbeat/venv/bin/pip install -r requirements.txt
```

### 2. Generate Certificates

```bash
# Create certificate directory
sudo mkdir -p /etc/slurm/heartbeat
sudo chmod 700 /etc/slurm/heartbeat

# Generate signing key
sudo openssl genrsa -out /etc/slurm/heartbeat/signing_key.pem 4096
sudo chmod 600 /etc/slurm/heartbeat/signing_key.pem

# Generate TLS certificates (or use BSC PKI)
sudo ./scripts/generate_certs.sh marenostrum /etc/slurm/heartbeat
```

### 3. Configure

```bash
# Copy example configuration
sudo cp examples/marenostrum/config.yaml /etc/slurm/heartbeat/config.yaml

# Edit configuration with site-specific values
sudo vim /etc/slurm/heartbeat/config.yaml
```

### 4. Install Systemd Service

```bash
# Install service file
sudo cp systemd/slurm-heartbeat.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable slurm-heartbeat

# Start service
sudo systemctl start slurm-heartbeat

# Check status
sudo systemctl status slurm-heartbeat
```

### 5. Verify Deployment

```bash
# Check logs
sudo journalctl -u slurm-heartbeat -f

# Check metrics
curl http://localhost:9090/metrics

# Check health endpoint
curl -k https://localhost:8443/health

# Check readiness endpoint (requires mTLS client cert)
curl --cert cert.pem --key key.pem --cacert ca.pem https://localhost:8443/readiness
```

## Files in This Directory

| File | Purpose |
|------|---------|
| `README.md` | This guide |
| `config.yaml` | MareNostrum5-specific configuration |
| `setup.sh` | Automated setup script |
| `verify.sh` | Verification script |
| `requirements.txt` | Python dependencies |

## Important Notes

### Production Deployment
MareNostrum5 supports systemd services for production deployment. Use the systemd service file for reliability and automatic restart.

### TLS Certificates
For production with EFP federation, use certificates from:
- BSC's internal PKI, or
- EFP CA (when available), or
- Your organization's PKI

Self-signed certificates are only for testing.

### Slurm REST API
The Slurm REST API (`slurmrestd`) should be available at `http://localhost:6820`. Verify:

```bash
curl -s http://localhost:6820/slurm/v0.0.39/ping
```

### EFP Federation
When EFP federation peers are available, configure them in `config.yaml`:

```yaml
client:
  federation:
    peers:
      - name: "lumi"
        endpoint: "https://lumi.example.com:8443/heartbeat"
        site: "CSC Finland"
        timeout_seconds: 30
```

## Troubleshooting

### "Service not found"
```bash
sudo systemctl daemon-reload
sudo systemctl status slurm-heartbeat
```

### "Permission denied" for certificates
```bash
sudo chmod 600 /etc/slurm/heartbeat/*.pem
sudo chmod 644 /etc/slurm/heartbeat/*.crt
```

### "Slurm REST API not responding"
Check Slurm REST API status:
```bash
sudo systemctl status slurmrestd
```

## References

- [BSC MareNostrum Documentation](https://docs.bsc.es/)
- [MareNostrum5 System Overview](https://www.bsc.es/marenostrum)
- [Slurm on MareNostrum5](https://docs.bsc.es/slurm/)
