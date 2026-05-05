# Slurm Heartbeat on Leonardo (CRESCO Italy)

This directory contains configuration and scripts for running Slurm Heartbeat on the Leonardo supercomputer operated by CRESCO in Italy.

## Overview

Leonardo is one of Europe's most powerful supercomputers, operated by CRESCO (European Centre for Research and High Performance Computing) in Italy. This guide covers **production deployment** using systemd services.

## Quick Start

### 1. Install Dependencies

```bash
sudo python3 -m venv /opt/slurmheartbeat/venv
sudo /opt/slurmheartbeat/venv/bin/pip install -r requirements.txt
```

### 2. Generate Certificates

```bash
sudo mkdir -p /etc/slurm/heartbeat
sudo openssl genrsa -out /etc/slurm/heartbeat/signing_key.pem 4096
sudo chmod 600 /etc/slurm/heartbeat/signing_key.pem
sudo ./scripts/generate_certs.sh leonardo /etc/slurm/heartbeat
```

### 3. Configure

```bash
sudo cp examples/leonardo/config.yaml /etc/slurm/heartbeat/config.yaml
sudo vim /etc/slurm/heartbeat/config.yaml
```

### 4. Install Systemd Service

```bash
sudo cp systemd/slurm-heartbeat.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable slurm-heartbeat
sudo systemctl start slurm-heartbeat
sudo systemctl status slurm-heartbeat
```

### 5. Verify Deployment

```bash
sudo journalctl -u slurm-heartbeat -f
curl http://localhost:9090/metrics
curl -k https://localhost:8443/health
```

## Files in This Directory

| File | Purpose |
|------|---------|
| `README.md` | This guide |
| `config.yaml` | Leonardo-specific configuration |
| `setup.sh` | Automated setup script |
| `verify.sh` | Verification script |
| `requirements.txt` | Python dependencies |

## Important Notes

### Production Deployment
Leonardo supports systemd services for production deployment.

### TLS Certificates
For production with EFP federation, use certificates from CRESCO's internal PKI or EFP CA (when available).

### Slurm REST API
Verify Slurm REST API is available:
```bash
curl -s http://localhost:6820/slurm/v0.0.39/ping
```

## References

- [CRESCO Leonardo Documentation](https://www.cresco.it/)
- [Leonardo System Overview](https://www.esciencecenter.nl/leonardo/)
