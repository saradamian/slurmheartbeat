# Slurm Heartbeat - Platform-Specific Deployment Examples

This directory contains deployment examples for various EuroHPC systems and other HPC clusters.

## Available Examples

| System | Operator | Deployment Model | Link |
|--------|----------|------------------|------|
| **Snellius** | SURF Netherlands | User-space | [examples/snellius/](snellius/) |
| **LUMI** | CSC Finland | Production (systemd) | [examples/lumi/](lumi/) |
| **MareNostrum5** | BSC Spain | Production (systemd) | [examples/marenostrum/](marenostrum/) |
| **Leonardo** | CRESCO Italy | Production (systemd) | [examples/leonardo/](leonardo/) |
| **JUPITER** | FZ Jülich Germany | Production (systemd) | [examples/jupiter/](jupiter/) |
| **MeluXina** | LuxProvide Luxembourg | Production (systemd) | [examples/meluxina/](meluxina/) |
| **Vega** | Slovenia | User-space | [examples/vega/](vega/) |
| **Isambard-AI** | UK | User-space | [examples/isambard-ai/](isambard-ai/) |
| **DEUCALION** | Spain | User-space | [examples/deucalion/](deucalion/) |
| **DAEDALUS** | Portugal | User-space | [examples/daedalus/](daedalus/) |
| **ARRHENIUS** | Sweden | User-space | [examples/arrhenius/](arrhenius/) |

## Quick Start

1. **Choose your system** from the table above
2. **Follow the deployment guide** in the system-specific directory
3. **Configure** for your site (certificates, federation peers, etc.)
4. **Deploy** using the provided scripts

## Deployment Models

### Production (systemd)
- Requires root/sudo access
- Uses systemd service for process management
- Logs to `/var/log/slurm/`
- Config in `/etc/slurm/heartbeat/`
- Certificates in `/etc/slurm/heartbeat/`

### User-space
- No root access required
- Uses screen/tmux or background processes
- Logs to `$HOME/logs/slurmheartbeat/`
- Config in `$HOME/.slurm/heartbeat/`
- Certificates in `$HOME/.slurm/heartbeat/`

## EFP Federation Configuration

When EFP federation peers are available, configure them in your `config.yaml`:

```yaml
client:
  federation:
    peers:
      - name: "lumi"
        endpoint: "https://lumi.example.com:8443/heartbeat"
        site: "CSC Finland"
        timeout_seconds: 30
```

## References

- [Main Documentation](../docs/)
- [Installation Guide](../docs/INSTALLATION.md)
- [Deployment Guide](../docs/DEPLOYMENT.md)
- [EFP Federation Platform](https://www.eurohpc-ju.europa.eu/supercomputers/eurohpc-federation-platform_en)
