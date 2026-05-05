# Slurm Heartbeat - CHANGELOG

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-05-04

### Critical Fixes (Audit 2026-05-02)

#### Metrics Initialization Order
- **Fixed metrics server initialization** - `MetricsServer` now instantiated before `ReadinessPublisher`
  - Configured Prometheus port is now respected (no more default 9090 override)
  - Metrics server starts exactly once (no double-starting)
  - Shared `MetricsServer` instance passed to all components

#### Certificate Subject Parsing
- **Fixed mTLS peer-name extraction** for nested RDN certificate format
  - `publisher.py` and `receiver.py` now handle standard `ssl.getpeercert()` nested format: `((("commonName", "value"),),)`
  - Added `_extract_cn_from_subject()` helper method for both classes
  - Tests updated to use realistic nested certificate subject format

#### Client/Server Decoupling
- **Fixed publisher readiness independence** - Readiness generation no longer blocked by `client.enabled=false`
  - Collector/normalizer always initialized in publisher mode
  - `client.enabled` only controls outgoing heartbeat sending
  - `/readiness` endpoint works independently of client mode

#### Collection Health
- **Fixed double Slurm collection** - Single collection per loop interval
  - `_check_slurmctld_reachable()` no longer calls `collector.collect()` separately
  - Reachability derived from collection result (single pass)
  - Reduced Slurm REST API traffic by 50%

#### Maintenance File Check
- **Fixed maintenance file check** - Replaced `anyio.Path` with standard `pathlib.Path`
  - Removed undocumented `anyio` dependency
  - Configurable maintenance file path (default: `/var/run/slurm/heartbeat/maintenance`)

### High Priority Fixes

#### Readiness Signing
- **Added readiness document signing** in `publisher.py`
  - `signing_key_file` config option for private key
  - Readiness documents signed before serving `/readiness`
  - Fail-open behavior (unsigned document served if signing fails)

#### Legacy P2P Feature Flag
- **Added `enable_legacy_p2p` config field** in `ServerConfig`
  - Defaults to `False` (legacy peer heartbeat disabled by default)
  - Feature flag properly parsed from YAML config
  - Reduces code surface until EFP confirms push transport requirement

#### Peer Public Key Wiring
- **Fixed peer public key loading** - Keys now accessible to receiver
  - `federation.peer_public_keys` loaded into both `client.federation` and `server.peer_public_keys`
  - Receiver can access configured peer keys for signature verification
  - Config loading preserves `server.allowed_sites` without overwriting

### Medium Priority Fixes

#### Documentation Cleanup
- **Updated collector docstring** - Reflects actual implementation (slurmrestd only)
  - Removed false claims about OpenMetrics/scontrol/sinfo fallbacks
  - Added note about future work for additional data sources

- **Consolidated documentation** - Removed duplicate "production ready" claims
  - `IMPLEMENTATION_SUMMARY.md` and `FINAL_VERIFICATION_REPORT.md` updated with conservative language
  - Single living document approach (README.md + CHANGELOG.md)

#### Configuration Cleanup
- **Removed unimplemented config sections** from `config.example.yaml`
  - Alerting, security, rate limiting, performance, compression sections removed
  - Only implemented configuration options remain in example file
  - Aspirational behavior moved to ADRs

#### Packaging Fixes
- **Added `py.typed` file** - PEP 561 compliance for type hints
- **Removed unused dependencies** from `pyproject.toml` and `requirements.txt`
  - `pydantic` removed (code uses dataclasses)
  - `aiosmtplib` removed (email alerting not implemented)
  - `aioredis`, `sentry-sdk` removed (not implemented)

#### Metadata Updates
- **Updated project URLs** - Replaced `your-org` placeholders with actual repository
  - `README.md`, `pyproject.toml`, `CHANGELOG.md`, `systemd/slurm-heartbeat.service`
  - Contact information updated

### Tests
- **117/117 tests passing** (11 new tests added)
- **Ruff linting clean** - All checks pass
- **Mypy clean** - 0 type errors
- **Added tests for nested certificate format** in `test_server.py`
- **Added tests for metrics initialization order** in `test_metrics.py`
- **Added lifecycle tests** in `test_lifecycle.py` (double-start prevention, feature flag bypass)

### Known Limitations
- Legacy `HeartbeatMessage` protocol still supported alongside EFP `ReadinessMessage`
- End-to-end integration tests with real TLS certificates not yet implemented
- `verify_signature()` still expects PEM bytes (not key objects)
- Partition/resource-class hints not yet implemented in readiness schema

---

## [0.3.0] - 2026-05-02

### Security Fixes (Audit 2026-05-02)

#### Critical
- **Fixed outgoing heartbeat signing** - Added `tls` field to `HeartbeatClientConfig` and proper key object handling
  - `sign()` now accepts both `RSAPrivateKey` objects and PEM bytes
  - Fail-closed behavior on signing errors (no unsigned messages sent)
  - Client TLS configuration properly parsed from YAML

#### High
- **Fixed mTLS peer certificate extraction** in `publisher.py` and `receiver.py`
  - Properly handles both dict format (standard SSL) and DER bytes format
  - Real mTLS client certificates now accepted instead of being rejected

- **Fixed authorization wiring** in `receiver.py`
  - `_allowed_members` now initialized from `config.allowed_sites`
  - Authorization checks work correctly with configured site list

- **Fixed Prometheus registry** - Custom registry now passed to `start_http_server`
  - `slurmheartbeat_*` metrics now properly exposed

- **Fixed `client.enabled` flag** - Properly respected in `main.py`
  - Outgoing heartbeats disabled when `client.enabled: false`
  - Readiness generation continues independently

#### Medium
- **Fixed metrics singleton** - Shared `MetricsServer` instance passed to `ReadinessPublisher`
  - No double-starting of metrics server

- **Fixed signal derivation** - Readiness signals derived from actual health checks
  - `slurmctld_reachable` and `maintenance` derived from actual checks instead of hardcoded

#### Low
- **Added client TLS section** to `config.example.yaml`
  - Complete example configuration for client-side mTLS and signing

### Improvements
- **Documentation consolidation** - Removed redundant verification/implementation reports
  - Key information merged into README.md and CHANGELOG.md
  - Reduced from 23 to 7 core documentation files

### Tests
- **106/106 tests passing** (up from 52)
- **Ruff linting clean** - All checks pass
- **Module execution verified** - `python -m slurmheartbeat --help` works

### Known Limitations
- Legacy `HeartbeatMessage` protocol still supported alongside EFP `ReadinessMessage`
- End-to-end integration tests with real TLS certificates not yet implemented
- `verify_signature()` still expects PEM bytes (not key objects)

---

## [0.2.0] - 2026-01-XX

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

[0.1.0]: https://github.com/saradamian/slurmheartbeat/releases/tag/v0.1.0
