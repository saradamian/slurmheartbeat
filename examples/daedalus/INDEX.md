# Slurm Heartbeat - DAEDALUS (Portugal)

This directory contains configuration and scripts for running Slurm Heartbeat on the DAEDALUS supercomputer.

## Quick Links

- [README.md](README.md) - Full deployment guide
- [config.yaml](config.yaml) - Configuration template
- [setup.sh](setup.sh) - Automated setup script
- [verify.sh](verify.sh) - Verification script

## Deployment Model

**User-space deployment**

## Prerequisites

- Python 3.10+
- Virtual environment
- Slurm 21.08+ with REST API enabled

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/saradamian/slurmheartbeat.git
cd slurmheartbeat

# 2. Install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Run setup
./examples/daedalus/setup.sh

# 4. Verify
./examples/daedalus/verify.sh
```

## Files

| File | Purpose |
|------|---------|
| `README.md` | Full deployment guide |
| `config.yaml` | DAEDALUS-specific configuration |
| `setup.sh` | Automated setup script |
| `verify.sh` | Verification script |
| `requirements.txt` | Python dependencies |

## References

- [DAEDALUS Supercomputer](https://www.daedalus.pt/)
