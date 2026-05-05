# Slurm Heartbeat on Vega (Slovenia)

This directory contains configuration and scripts for running Slurm Heartbeat on the Vega supercomputer in Slovenia.

## Overview

Vega is a supercomputer in Slovenia, part of the EuroHPC network. This guide covers **user-space deployment** where systemd services may not be available.

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
cp examples/vega/config.yaml $HOME/.slurm/heartbeat/config.yaml
```

### 4. Generate Certificates

```bash
openssl genrsa -out $HOME/.slurm/heartbeat/signing_key.pem 4096
chmod 600 $HOME/.slurm/heartbeat/signing_key.pem
./scripts/generate_certs.sh vega $HOME/.slurm/heartbeat
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
| `config.yaml` | Vega-specific configuration |
| `setup.sh` | Automated setup script |
| `verify.sh` | Verification script |
| `requirements.txt` | Python dependencies |

## Important Notes

### No Systemd Services
Vega may not allow users to run systemd services. Use screen/tmux or background processes instead.

### Slurm REST API
Verify Slurm REST API is available:
```bash
curl -s http://localhost:6820/slurm/v0.0.39/ping
```

## References

- [Vega Supercomputer](https://www.vega.si/)
