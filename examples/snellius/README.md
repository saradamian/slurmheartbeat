# Slurm Heartbeat on Snellius (SURF)

This directory contains configuration and scripts for running Slurm Heartbeat on the Snellius HPC cluster at SURF.

## Overview

Snellius is the Dutch national supercomputer operated by SURF. This guide covers **user-space deployment** where you cannot use systemd services.

## Key Differences from Standard Deployment

| Component | Standard (systemd) | Snellius (user space) |
|-----------|-------------------|----------------------|
| **Installation** | `/opt/slurmheartbeat/` | `$HOME/slurmheartbeat/` |
| **Python env** | System venv | User venv with modules |
| **Service** | `systemctl start` | `screen`/`tmux`/`nohup` |
| **Config** | `/etc/slurm/heartbeat/` | `$HOME/.slurm/heartbeat/` |
| **Logs** | `/var/log/slurm/` | `$HOME/logs/slurmheartbeat/` |
| **Certificates** | `/etc/slurm/heartbeat/` | `$HOME/.slurm/heartbeat/` |

## Quick Start

### 1. Load Software Environment

```bash
ssh snellius.surf.nl
module load 2025
module load Python/3.11.6
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
./examples/snellius/setup.sh
```

This creates:
- `$HOME/.slurm/heartbeat/config.yaml`
- `$HOME/.slurm/heartbeat/signing_key.pem`
- `$HOME/.slurm/heartbeat/server.crt` and `server.key`
- `$HOME/logs/slurmheartbeat/`

### 4. Run

**Option A: Screen session (recommended for testing)**
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

**Option C: Slurm job (for testing only)**
```bash
sbatch examples/snellius/run_heartbeat.slurm
```

## Files in This Directory

| File | Purpose |
|------|---------|
| `README.md` | This guide |
| `config.yaml` | Snellius-specific configuration |
| `setup.sh` | Automated setup script |
| `run_heartbeat.slurm` | Slurm job template for testing |
| `verify.sh` | Verification script |
| `requirements.txt` | Python dependencies |

## Important Notes

### No Systemd Services
Snellius does not allow users to run systemd services. Use one of the alternatives above.

### Login Node Restrictions
- Do **not** run heavy workloads on login nodes
- For production, request a dedicated node via Slurm job
- Keep resource usage minimal on login nodes

### Slurm REST API
The Slurm REST API (`slurmrestd`) should be available at `http://localhost:6820`. Verify:

```bash
curl -s http://localhost:6820/slurm/v0.0.39/ping
```

### TLS Certificates
For testing, use self-signed certificates. For production with EFP federation, you'll need certificates from the EFP CA (when available) or your site's PKI.

## Troubleshooting

### "Module not found: slurm"
```bash
module load 2025
module load Python/3.11.6
```

### "Slurm REST API not responding"
The REST API may not be available on all nodes. Try:
```bash
curl -s http://localhost:6820/slurm/v0.0.39/ping
```

If it fails, check with SURF support or verify Slurm installation.

### "Permission denied" for certificates
```bash
chmod 600 $HOME/.slurm/heartbeat/*.pem
chmod 644 $HOME/.slurm/heartbeat/*.crt
```

## References

- [SURF Snellius Documentation](https://servicedesk.surf.nl/wiki/spaces/WIKI/pages/30660184/Snellius)
- [Slurm on Snellius](https://servicedesk.surf.nl/wiki/spaces/WIKI/pages/30660221/SLURM+batch+system)
- [Installing Software on Snellius](https://servicedesk.surf.nl/wiki/spaces/WIKI/pages/30660267/Software+policy+Snellius)
