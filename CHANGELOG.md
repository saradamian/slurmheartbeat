# Slurm Heartbeat - CHANGELOG

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-01-XX

### Security Fixes

#### Critical
- **Fixed certificate generation bug** in `slurmheartbeat/protocol/security.py`
  - Replaced non-existent `x509.utils.utcnow()` with `datetime.datetime.utcnow()`
  - Certificate generation now works correctly for TLS setup

#### High
- **Migrated to asymmetric RSA signing** in `slurmheartbeat/protocol/message.py`
  - Replaced HMAC with shared secret with RSA-PKCS1v15 asymmetric signing
  - Each federation member now has unique key pairs
  - No shared secrets required across federation

- **Added certificate-based authorization** in `slurmheartbeat/server/receiver.py`
  - Added `set_allowed_members()` and `is_member_allowed()` methods
  - Extracts CN from client certificates for authorization
  - Returns 403 Unauthorized for unapproved federation members

#### Medium-High
- **Added rate limiting** in `slurmheartbeat/server/receiver.py`
  - Implemented sliding window rate limiter (100 requests/minute per IP)
  - Returns 429 Too Many Requests when limit exceeded
  - Protects against heartbeat flood attacks

### Tests
- All 52 tests passing
- 6 non-blocking warnings about unawaited coroutines in test mocks

## [0.1.0] - 2025-01-09

### Added

#### Core Functionality
- Heartbeat message protocol with JSON serialization and deserialization
- TLS 1.3 mutual authentication support
- Certificate generation and rotation utilities
- Async HTTP client for Slurm REST API integration
- Heartbeat sender with retry logic and exponential backoff
- Heartbeat receiver server with aioHTTP
- Peer state tracking (healthy, degraded, unhealthy)
- Prometheus metrics export (counters, gauges, histograms)

#### Components
- `SlurmCollector` for gathering cluster metrics from Slurm REST API
- `HeartbeatSender` for sending heartbeats to federation peers
- `HeartbeatReceiver` for receiving heartbeats from peers
- `FederationState` for managing peer health states
- `MetricsServer` for Prometheus metrics export
- `HeartbeatDaemon` main entry point coordinating all components

#### Configuration
- YAML-based configuration with support for:
  - Client settings (interval, timeout, retry)
  - Server settings (listen address, port, TLS)
  - Federation peers configuration
  - Prometheus metrics configuration
  - Alerting configuration (webhooks, email)
  - Security settings (rate limiting, access control)
  - Performance tuning (connection pooling, resource limits)

#### Documentation
- Comprehensive research documents on EFP requirements
- Testing guide with examples
- Deployment guide with production checklist
- Security guide with threat model and hardening
- Test environment setup guide for local Slurm federation

#### Scripts
- Certificate generation script (`generate_certs.sh`)
- Test runner script (`run_tests.sh`)
- Systemd service file for production deployment

#### Tests
- Unit tests for protocol serialization/deserialization
- Unit tests for client sender with retry logic
- Unit tests for server receiver and state management
- Unit tests for Prometheus metrics
- Integration tests for full heartbeat flow
- Comprehensive test fixtures in `conftest.py`

### Changed
- Updated `main.py` to integrate all components with metrics collection
- Fixed configuration loading to properly access nested config objects

### Known Issues
- TLS certificate paths default to `/etc/slurm/heartbeat/` - update for testing
- Some lint warnings in test files (unused variables) - non-functional
- Integration with EFP federation controller not yet implemented (pending EFP specification)

### Future Work
- Contact EFP team to clarify technical requirements
- Implement EFP-specific authentication mechanisms
- Add support for certificate rotation automation
- Implement cross-site job routing hints
- Add predictive failure detection
- Integrate with federated accounting systems

---

[0.1.0]: https://github.com/your-org/slurmheartbeat/releases/tag/v0.1.0
