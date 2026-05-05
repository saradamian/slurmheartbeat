# Slurm Heartbeat - Leonardo (CRESCO Italy)

This directory contains configuration and scripts for running Slurm Heartbeat on the Leonardo supercomputer.

## Quick Links

- [README.md](README.md) - Full deployment guide
- [config.yaml](config.yaml) - Configuration template
- [setup.sh](setup.sh) - Automated setup script
- [verify.sh](verify.sh) - Verification script

## Deployment Model

**Production deployment with systemd services**

## Prerequisites

- Root/sudo access for installation
- Python 3.10+ (system Python)
- Slurm 21.08+ with REST API enabled
- OpenSSL 1.1.1+ for TLS 1.3

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/saradamian/slurmheartbeat.git
cd slurmheartbeat

# 2. Install dependencies
sudo python3 -m venv /opt/slurmheartbeat/venv
sudo /opt/slurmheartbeat/venv/bin/pip install -r requirements.txt

# 3. Run setup (as root)
sudo ./examples/leonardo/setup.sh

# 4. Verify
sudo ./examples/leonardo/verify.sh
```

## Files

| File | Purpose |
|------|---------|
| `README.md` | Full deployment guide |
| `config.yaml` | Leonardo-specific configuration |
| `setup.sh` | Automated setup script (requires sudo) |
| `verify.sh` | Verification script |
| `requirements.txt` | Python dependencies |

## References

- [CRESCO Leonardo Documentation](https://www.cresco.it/)
- [Leonardo System Overview](https://www.esciencecenter.nl/leonardo/)
