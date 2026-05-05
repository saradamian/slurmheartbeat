# Slurm Heartbeat on JUPITER (Jülich Germany)

This directory contains configuration and scripts for running Slurm Heartbeat on the JUPITER exascale supercomputer operated by Forschungszentrum Jülich in Germany.

## Overview

JUPITER is Europe's first exascale supercomputer, operated by Forschungszentrum Jülich in Germany. This guide covers **production deployment** using systemd services.

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
sudo ./scripts/generate_certs.sh jupiter /etc/slurm/heartbeat
```

### 3. Configure

```bash
sudo cp examples/jupiter/config.yaml /etc/slurm/heartbeat/config.yaml
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
| `config.yaml` | JUPITER-specific configuration |
| `setup.sh` | Automated setup script |
| `verify.sh` | Verification script |
| `requirements.txt` | Python dependencies |

## Important Notes

### Production Deployment
JUPITER supports systemd services for production deployment.

### TLS Certificates
For production with EFP federation, use certificates from FZ Jülich's internal PKI or EFP CA (when available).

### Slurm REST API
Verify Slurm REST API is available:
```bash
curl -s http://localhost:6820/slurm/v0.0.39/ping
```

## References

- [FZ Jülich JUPITER Documentation](https://www.fz-juelich.de/en/jupiter)
- [JUPITER System Overview](https://www.fz-juelich.de/en/jupiter/overview)
