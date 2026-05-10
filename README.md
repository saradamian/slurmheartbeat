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
- Slurm 21.08+ (with REST API support)
- OpenSSL 1.1.1+ (for TLS 1.3)

### Installation

```bash
# Clone the repository
git clone https://github.com/saradamian/slurmheartbeat.git
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

## EFP Scope & Architecture

This project implements a **readiness publisher** for the EuroHPC Federation Platform (EFP), as recommended in [`docs/EFP_HEARTBEAT_RECOMMENDATION.md`](docs/EFP_HEARTBEAT_RECOMMENDATION.md).

### What This Does

Per EFP recommendation, this is a **narrow readiness signal**, not a replacement for:
- Slurm native federation
- Prometheus/OpenMetrics detailed telemetry
- EFP scheduler or allocation logic
- Cross-site workflow orchestration

The system produces a compact readiness document answering:
> "Can this site safely receive federated work right now, and why or why not?"

### Architecture

Each site runs a local readiness publisher that:
1. **Collects** local Slurm state via `slurmrestd` (read-only)
2. **Normalizes** to EFP schema (no user/job/account details)
3. **Publishes** signed `/readiness` and `/metrics` endpoints
4. **Optionally pushes** heartbeats to federation peers

### EFP Alignment

The implementation follows EFP recommendations:
- **Read-only operation**: No modification of Slurm state
- **mTLS authentication**: Secure cross-site communication
- **TTL-based freshness**: Cache control for consumers
- **No user/job/account data**: Privacy-preserving aggregation
- **Authorization independent from signature**: Valid signature ≠ automatic access

### Future Work (Not Yet Implemented)

The following EFP gaps remain open for federation-wide decisions:
- **EFP Identity System**: No standardized identity system (EFP PKI vs. site vs. MyAccessID) - requires EFP-wide decision
- **Consumption Pattern**: No standardized signal consumption pattern - requires EFP stakeholder decision
- **Advanced ML-based Prediction**: Queue prediction uses simple heuristics; ML-based prediction requires EFP consensus on data sharing

**Note**: The following capabilities are **now implemented** as experimental features:
- ✅ **Federated Capacity Discovery** - Peer discovery and capacity fetching (see [`docs/FEDERATION.md`](docs/FEDERATION.md))
- ✅ **Queue Prediction** - Basic queue pressure and wait time prediction (see [`docs/FEDERATION.md`](docs/FEDERATION.md))
- ✅ **Metrics Aggregation** - Federated metrics aggregation for dashboards (see [`docs/FEDERATION.md`](docs/FEDERATION.md))

These features are **feature-flagged** (`federation.enabled: true` in config) and require manual peer configuration. They are **prototype implementations** suitable for testing and feedback collection, but not yet production-ready for widespread deployment.

---

## Documentation

### Core Documentation

- [`docs/EFP_HEARTBEAT_RECOMMENDATION.md`](docs/EFP_HEARTBEAT_RECOMMENDATION.md) - EFP requirements, scope, and recommendations
- [`docs/ADR.md`](docs/ADR.md) - Architecture Decision Records (ADR-001 through ADR-008)

### Installation and Operations

- [`docs/INSTALLATION.md`](docs/INSTALLATION.md) - Complete installation and deployment guide
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) - Production deployment considerations
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) - Operations, monitoring, and maintenance
- [`docs/SECURITY.md`](docs/SECURITY.md) - Security model, mTLS, and signing
- [`docs/TESTING.md`](docs/TESTING.md) - Testing procedures and lifecycle tests

### Reference

- [`config.example.yaml`](config.example.yaml) - Configuration reference
- [`docs/GLOSSARY.md`](docs/GLOSSARY.md) - Terminology and definitions
- [`docs/CONSOLIDATION_SUMMARY.md`](docs/CONSOLIDATION_SUMMARY.md) - Documentation consolidation history

## Implementation Status

**⚠️ ALPHA READINESS ADAPTER** - Core functionality working, production hardening in progress

- **Tests**: 117/117 passing
- **Linting**: Ruff clean
- **Type Checking**: Mypy clean (0 errors)
- **Critical Fixes**: 14/14 audit findings addressed (all fixed)
- **EFP Alignment**: Schema compliant, lifecycle fixes complete

### Resolved Audit Findings (2026-05-04)

| # | Finding | Status |
|---|---------|--------|
| 1 | Metrics double-start | ✅ Fixed |
| 2 | Publisher readiness gated by `client.enabled` | ✅ Fixed |
| 3 | Readiness signing not wired through YAML | ✅ Fixed |
| 4 | Controller reachability from node count | ✅ Fixed |
| 5 | `enable_legacy_p2p` not parsed from YAML | ✅ Fixed |
| 6 | Dynamic `peer_public_keys` attribute | ✅ Fixed |
| 7 | Prometheus exposition duplication | ✅ Fixed |
| 8 | Documentation overclaims readiness | ✅ Fixed |
| 9 | Unimplemented config sections | ✅ Fixed |
| 10 | Maintenance mode hardcoded | ✅ Configurable via `server.maintenance_path` |
| 11 | Type checking not passing | ✅ Fixed (0 mypy errors, Ruff clean) |
| 12 | Missing lifecycle tests | ✅ Fixed (7 new tests in `test_lifecycle.py`) |
| 13 | Slurm input documentation | ✅ Fixed (REST API only, not OpenMetrics) |
| 14 | Repository metadata consistency | ✅ Fixed (all URLs point to `saradamian/slurmheartbeat`) |

### Remaining Work (Lower Priority, Non-Blocking)

| # | Finding | Priority | Status |
|---|---------|----------|--------|
| 13 | Slurm input documentation | Low | ✅ Fixed (REST API only, not OpenMetrics) |

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=slurmheartbeat --cov-report=html

# Run specific test file
pytest tests/test_schema.py -v
```

**Current Status**: ✅ 117/117 tests passing

## Documentation

- [Installation Guide](docs/INSTALLATION.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Operations Guide](docs/OPERATIONS.md)
- [Security Guide](docs/SECURITY.md)
- [Testing Guide](docs/TESTING.md)
- [Architecture Decisions](docs/ADR.md)
- [EFP Recommendation](docs/EFP_HEARTBEAT_RECOMMENDATION.md)
- [Contributing](CONTRIBUTING.md)

### Platform-Specific Examples

- [Snellius (SURF)](examples/snellius/) - User-space deployment for Snellius HPC (Netherlands)
- [LUMI (CSC)](examples/lumi/) - Production deployment with systemd (Finland)
- [MareNostrum5 (BSC)](examples/marenostrum/) - Production deployment with systemd (Spain)
- [Leonardo (CRESCO)](examples/leonardo/) - Production deployment with systemd (Italy)
- [JUPITER (FZ Jülich)](examples/jupiter/) - Production deployment with systemd (Germany)
- [MeluXina (LuxProvide)](examples/meluxina/) - Production deployment with systemd (Luxembourg)
- [Vega](examples/vega/) - User-space deployment (Slovenia)
- [Isambard-AI](examples/isambard-ai/) - User-space deployment (UK)
- [DEUCALION](examples/deucalion/) - User-space deployment (Spain)
- [DAEDALUS](examples/daedalus/) - User-space deployment (Portugal)
- [ARRHENIUS](examples/arrhenius/) - User-space deployment (Sweden)

**See [examples/INDEX.md](examples/INDEX.md) for a complete overview of all platform examples.**

### Containerized Deployment

- [Docker Deployment](docs/CONTAINER_DEPLOYMENT.md) - Run in Docker containers with Docker Compose
- [Dockerfile](Dockerfile) - Container image definition
- [docker-compose.yml](docker-compose.yml) - Multi-service setup with Prometheus

## Status Definitions

Per EFP recommendation:

| Status | Meaning | When to Use |
|--------|---------|-------------|
| `ready` | Accepting federated work | All checks pass |
| `limited` | Degraded but reachable | High queue pressure, partial maintenance |
| `draining` | Stopping intake | Maintenance mode, intentional shutdown |
| `unavailable` | Unreachable/unhealthy | slurmctld down, >50% nodes down |
| `unknown` | Stale/contradictory | No data, collection errors |

## Known Limitations

1. **Legacy P2P**: `HeartbeatMessage` (legacy) and `ReadinessMessage` (EFP) both supported. Legacy protocol is deprecated but kept for backward compatibility.
2. **Signature Verification**: `verify_signature()` expects PEM bytes (not key objects).
3. **End-to-End Tests**: No integration tests with real TLS certificates (all tests use mocks).
4. **Readiness Signing**: Optional - requires `signing_key_file` configuration in publisher.
5. **Slurm Input**: Only REST API (`slurmrestd`) supported. OpenMetrics not yet implemented.

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

- Project Issues: [GitHub Issues](https://github.com/saradamian/slurmheartbeat/issues)
- Email: [contact@saradamian.org](mailto:contact@saradamian.org)
