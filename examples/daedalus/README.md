# Slurm Heartbeat on DAEDALUS (Portugal)

This directory contains configuration and scripts for running Slurm Heartbeat on the DAEDALUS supercomputer in Portugal.

## Overview

DAEDALUS is a supercomputer in Portugal, part of the EuroHPC network. This guide covers **user-space deployment**.

## Quick Start

### 1. Load Software Environment

```bash
module load Python/3.10
```

### 2. Install Slurm Heartbeat

```bash
cd $HOME
git clone https://github.com/saradamian/slurmheartbeat.git
cd slurmheartbeat
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

```bash
mkdir -p $HOME/.slurm/heartbeat
mkdir -p $HOME/logs/slurmheartbeat
cp examples/daedalus/config.yaml $HOME/.slurm/heartbeat/config.yaml
```

### 4. Generate Certificates

```bash
openssl genrsa -out $HOME/.slurm/heartbeat/signing_key.pem 4096
chmod 600 $HOME/.slurm/heartbeat/signing_key.pem
./scripts/generate_certs.sh daedalus $HOME/.slurm/heartbeat
```

### 5. Run

**Option A: Screen session (recommended)**
```bash
screen -S slurmheartbeat
source $HOME/slurmheartbeat/venv/bin/activate
python -m slurmheartbeat --config $HOME/.slurm/heartbeat/config.yaml
# Detach: Ctrl+A, then D
```

**Option B: Background process**
```bash
nohup $HOME/slurmheartbeat/venv/bin/python -m slurmheartbeat \
  --config $HOME/.slurm/heartbeat/config.yaml \
  > $HOME/logs/slurmheartbeat/nohup.out 2>&1 &
```

## Files in This Directory

| File | Purpose |
|------|---------|
| `README.md` | This guide |
| `config.yaml` | DAEDALUS-specific configuration |
| `setup.sh` | Automated setup script |
| `verify.sh` | Verification script |
| `requirements.txt` | Python dependencies |

## Important Notes

### Slurm REST API
Verify Slurm REST API is available:
```bash
curl -s http://localhost:6820/slurm/v0.0.39/ping
```

## References

- [DAEDALUS Supercomputer](https://www.daedalus.pt/)
