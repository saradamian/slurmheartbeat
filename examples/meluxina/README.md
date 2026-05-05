# Slurm Heartbeat on MeluXina (Luxembourg)

This directory contains configuration and scripts for running Slurm Heartbeat on the MeluXina supercomputer operated by LuxProvide in Luxembourg.

## Overview

MeluXina is a powerful supercomputer operated by LuxProvide in Luxembourg, part of the EuroHPC network. This guide covers **production deployment** using systemd services.

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
sudo ./scripts/generate_certs.sh meluxina /etc/slurm/heartbeat
```

### 3. Configure

```bash
sudo cp examples/meluxina/config.yaml /etc/slurm/heartbeat/config.yaml
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
| `config.yaml` | MeluXina-specific configuration |
| `setup.sh` | Automated setup script |
| `verify.sh` | Verification script |
| `requirements.txt` | Python dependencies |

## Important Notes

### Production Deployment
MeluXina supports systemd services for production deployment.

### TLS Certificates
For production with EFP federation, use certificates from LuxProvide's internal PKI or EFP CA (when available).

### Slurm REST API
Verify Slurm REST API is available:
```bash
curl -s http://localhost:6820/slurm/v0.0.39/ping
```

## References

- [LuxProvide MeluXina Documentation](https://www.luxprovide.lu/)
- [MeluXina System Overview](https://www.meluxina.lu/)
