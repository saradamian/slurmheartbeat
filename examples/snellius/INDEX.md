# Slurm Heartbeat - Snellius (SURF) Example Configuration

This directory contains example files for deploying Slurm Heartbeat on the Snellius HPC cluster at SURF.

## Files

| File | Purpose |
|------|---------|
| `README.md` | Complete guide for Snellius deployment |
| `config.yaml` | Snellius-specific configuration template |
| `setup.sh` | Automated setup script |
| `run_heartbeat.slurm` | Slurm job template for testing |
| `verify.sh` | Verification script |

## Quick Start

```bash
# 1. Load modules and create venv
module load 2025
module load Python/3.11.6
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Run setup script
./examples/snellius/setup.sh

# 3. Verify installation
./examples/snellius/verify.sh

# 4. Start the daemon
screen -S slurmheartbeat
python -m slurmheartbeat --config $HOME/.slurm/heartbeat/config.yaml
```

## Important Notes

- **No systemd services** on Snellius - use `screen`, `tmux`, or `nohup`
- **User-space deployment** - all files in `$HOME`
- **Self-signed certificates** for testing - use site PKI for production
- **Slurm REST API** must be accessible (usually on compute nodes)

## References

- [Snellius Documentation](https://servicedesk.surf.nl/wiki/spaces/WIKI/pages/30660184/Snellius)
- [Slurm on Snellius](https://servicedesk.surf.nl/wiki/spaces/WIKI/pages/30660221/SLURM+batch+system)
- [Software Policy](https://servicedesk.surf.nl/wiki/spaces/WIKI/pages/30660267/Software+policy+Snellius)
