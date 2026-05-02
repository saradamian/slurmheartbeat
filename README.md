# Slurm Heartbeat for European Federated Platform (EFP)

A readiness publisher for the European Federated Platform (EFP) that answers:

> "Can this site safely receive federated work right now, and why or why not?"

## Overview

This project implements an EFP-aligned readiness signal that combines:
- Local Slurm state (nodes, partitions, jobs)
- Site reachability (slurmctld status)
- Maintenance intent
- Queue pressure indicators

**Per EFP recommendation**: This is a **readiness publisher**, not a replacement for Slurm federation, detailed metrics, or the EFP scheduler.

## Key Features

### EFP-Aligned Readiness Schema

The system produces a compact readiness document with:
- **Status**: `ready`, `limited`, `draining`, `unavailable`, or `unknown`
- **Signals**: slurmctld_reachable, maintenance, accepting_new_jobs, queue_pressure, etc.
- **Capacity hints**: idle_nodes, down_nodes, pending_jobs, running_jobs
- **TTL**: Cache control for consumers (data expires after TTL)
- **Signature**: Cryptographic verification of authenticity

### Dual-Mode Operation

- **Publisher Mode**: Serves `/readiness` (signed JSON) and `/metrics` (Prometheus) endpoints
- **Client Mode**: Collects Slurm state and sends signed heartbeats to federation peers
- **Both Modes**: Default operation combining both capabilities

### Security

- **mTLS**: Mutual TLS authentication for cross-site communication
- **Signature Verification**: Cryptographic signing of readiness documents
- **Authorization**: Separate access control (allowed_sites list)
- **Read-Only**: Does not modify Slurm state

## Quick Start

### Prerequisites

- Python 3.10+
- Slurm 21.08+ (with REST API or OpenMetrics support)
- OpenSSL 1.1.1+ (for TLS 1.3)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/slurmheartbeat.git
cd slurmheartbeat

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Generate TLS certificates (optional for testing)
./scripts/generate_certs.sh your-site-name /etc/slurm/heartbeat
# For testing: ./scripts/generate_certs.sh test /tmp

# Configure
cp config.example.yaml /etc/slurm/heartbeat/config.yaml
# Edit configuration as needed
```

### Running the Daemon

```bash
# Development mode with verbose logging
python -m slurmheartbeat -c config.yaml -v

# Run in publisher mode (serve /readiness endpoint)
python -m slurmheartbeat --mode publisher

# Run in client mode (send heartbeats to peers)
python -m slurmheartbeat --mode client

# Run in both modes (default)
python -m slurmheartbeat
```

### systemd Service

```bash
# Install service file
sudo cp systemd/slurm-heartbeat.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable slurm-heartbeat
sudo systemctl start slurm-heartbeat

# Check status
sudo systemctl status slurm-heartbeat

# View logs
sudo journalctl -u slurm-heartbeat -n 50
sudo journalctl -u slurm-heartbeat -f
```

### Quick Testing

```bash
# Check metrics
curl http://localhost:9090/metrics

# Check health endpoint
curl -k https://localhost:8443/health

# View readiness (requires mTLS client cert)
curl --cert cert.pem --key key.pem --cacert ca.pem https://localhost:8443/readiness
```

## Endpoints

### GET /readiness

Serves a signed readiness document.

**Authentication**: mTLS client certificate required

**Response** (200 OK):
```json
{
  "schema_version": "0.1",
  "site_id": "lumi",
  "cluster_name": "lumi-prod",
  "observed_at": "2026-05-01T21:30:00Z",
  "status": "ready",
  "fed_state": "ACTIVE",
  "reason": "scheduler_accepting_work",
  "ttl_seconds": 90,
  "signals": {
    "slurmctld_reachable": true,
    "slurm_federation_visible": true,
    "maintenance": false,
    "accepting_new_jobs": true,
    "queue_pressure": "normal",
    "critical_partitions_available": true
  },
  "capacity_hint": {
    "idle_nodes": 42,
    "down_nodes": 0,
    "drained_nodes": 3,
    "pending_jobs": 120,
    "running_jobs": 820
  }
}
```

### GET /metrics

Prometheus-compatible metrics.

### GET /health

Liveness check.

## Configuration

See `config.example.yaml` for a complete configuration reference.

Key configuration sections:
- `client` - Outgoing heartbeat settings (client mode)
- `server` - Incoming readiness serving settings (publisher mode)
- `tls` - TLS/SSL configuration (mTLS)
- `monitoring` - Prometheus metrics
- `federation` - List of federation peers (for client mode)
- `allowed_sites` - Authorization list for /readiness endpoint

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Slurm Federation                         │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Site A     │    │   Site B     │    │   Site C     │  │
│  │  ┌────────┐  │    │  ┌────────┐  │    │  ┌────────┐  │  │
│  │  │slurmctld│  │    │  │slurmctld│  │    │  │slurmctld│  │  │
│  │  └────┬───┘  │    │  └────┬───┘  │    │  └────┬───┘  │  │
│  │       │      │    │       │      │    │       │      │  │
│  │  ┌────▼────┐ │    │  ┌────▼────┐ │    │  ┌────▼────┐ │  │
│  │  │Readiness│ │    │  │Readiness│ │    │  │Readiness│ │  │
│  │  │Publisher│ │◄───┼──│Publisher│ │◄───┼──│Publisher│ │  │
│  │  └────┬────┘ │    │  └────┬────┘ │    │  └────┬────┘ │  │
│  │       │      │    │       │      │    │       │      │  │
│  │  ┌────▼────┐ │    │  ┌────▼────┐ │    │  ┌────▼────┐ │  │
│  │  │Collector│ │    │  │Collector│ │    │  │Collector│ │  │
│  │  └─────────┘ │    │  └─────────┘ │    │  └─────────┘ │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         └────────────────────┴────────────────────┘
                    Pull via /readiness or Push via heartbeat
```

## Documentation

- [`EFP_HEARTBEAT_RECOMMENDATION.md`](EFP_HEARTBEAT_RECOMMENDATION.md) - EFP requirements and recommendations
- [`EFP_IMPLEMENTATION_SUMMARY.md`](EFP_IMPLEMENTATION_SUMMARY.md) - Implementation details
- [`TECHNICAL_DESIGN.md`](TECHNICAL_DESIGN.md) - Detailed technical design
- [`docs/`](docs/) - Operations, security, and deployment guides

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=slurmheartbeat --cov-report=html

# Run specific test file
pytest tests/test_schema.py -v
```

**Current Status**: ✅ 95 tests passing

## Status Definitions

Per EFP recommendation:

| Status | Meaning | When to Use |
|--------|---------|-------------|
| `ready` | Accepting federated work | All checks pass |
| `limited` | Degraded but reachable | High queue pressure, partial maintenance |
| `draining` | Stopping intake | Maintenance mode, intentional shutdown |
| `unavailable` | Unreachable/unhealthy | slurmctld down, >50% nodes down |
| `unknown` | Stale/contradictory | No data, collection errors |

## What This Does NOT Do

Per EFP recommendation, this implementation:
- ❌ Does NOT replace Slurm federation
- ❌ Does NOT make job placement decisions
- ❌ Does NOT collect user/job/account details
- ❌ Does NOT automatically modify Slurm state
- ❌ Does NOT assume all sites run the same Slurm version

## Success Criteria

The implementation is successful if it can:
- ✅ Explain why a site is ready, limited, draining, unavailable, or unknown
- ✅ Stay accurate during maintenance and Slurm controller incidents
- ✅ Avoid leaking user/project data
- ✅ Be consumed by EFP monitoring or scheduling components without site-specific parsing
- ✅ Degrade safely when data is stale

## Development

### Adding a New Feature

1. Create a feature branch: `git checkout -b feat/your-feature`
2. Implement the feature
3. Add tests
4. Update documentation
5. Submit a pull request

### Code Style

- Type hints for all function signatures
- Docstrings for all public functions and classes
- 100-character line length maximum
- Follows PEP 8 with ruff linting

## Security

### Authentication

- Mutual TLS (mTLS) for all cross-site communication
- Certificate-based site identity verification
- Configurable access control lists (allowed_sites)

### Best Practices

1. **Certificate Management**: Rotate certificates annually
2. **Network Security**: Restrict heartbeat ports to federation members only
3. **Monitoring**: Enable alerting for unusual patterns
4. **Audit**: Regular review of access logs

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- EuroHPC Joint Undertaking for the EFP initiative
- Slurm Workload Manager community
- LUMI supercomputer team for early feedback

## Contact

- Project Issues: [GitHub Issues](https://github.com/your-org/slurmheartbeat/issues)
- Email: [your-email@example.com](mailto:your-email@example.com)
