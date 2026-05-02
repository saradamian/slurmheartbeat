# Slurm Heartbeat - Architecture Decision Record (ADR)

This document records key architectural decisions for the Slurm Heartbeat project.

## ADR-001: Implementation Language

**Date**: 2025-01-09  
**Status**: Accepted  
**Deciders**: Project Team

### Context

We need to choose an implementation language for the heartbeat daemon. Options considered:
- Python
- C (as Slurm plugin)
- Go
- Hybrid (C daemon + Python management)

### Decision

**Choose Python** for the initial proof-of-concept and production implementation.

### Rationale

1. **Rapid Development**: Python enables fast iteration and testing
2. **Rich Ecosystem**: Excellent libraries for async I/O, TLS, and monitoring
3. **Ease of Deployment**: No compilation required, easy dependency management
4. **Integration**: Good Slurm REST API support via HTTP clients
5. **Maintainability**: Easier for operations team to understand and modify

### Consequences

**Positive**:
- Faster time to market
- Easier to test and debug
- Lower barrier to contribution
- Good monitoring integration (Prometheus client)

**Negative**:
- External process (not part of slurmctld)
- Slightly higher resource overhead than C
- Version dependency management

### Alternatives Considered

- **C Plugin**: Tighter integration but requires Slurm source modification
- **Go**: Good performance but smaller ecosystem
- **Hybrid**: More complex, deferred to future phases

---

## ADR-002: Communication Protocol

**Date**: 2025-01-09  
**Status**: Accepted  
**Deciders**: Project Team

### Context

Need to define the communication protocol for heartbeat messages between federation members.

### Decision

**Use HTTPS with JSON payloads over TLS 1.3**.

### Rationale

1. **Standardization**: HTTPS is widely understood and supported
2. **Security**: TLS 1.3 provides strong encryption and authentication
3. **Simplicity**: JSON is easy to parse and debug
4. **Extensibility**: Easy to add new fields without breaking compatibility
5. **Tooling**: Excellent debugging tools (curl, browsers, etc.)

### Message Format

```json
{
  "version": "1.0",
  "timestamp": "2025-01-09T10:30:00Z",
  "cluster": {
    "id": "lumi-prod",
    "name": "LUMI Production",
    "site": "CSC Finland"
  },
  "status": "healthy",
  "resources": {
    "total_nodes": 4320,
    "active_nodes": 4318
  },
  "signature": "base64-encoded-signature"
}
```

### Consequences

**Positive**:
- Easy to implement and test
- Good interoperability
- Debuggable in production

**Negative**:
- JSON overhead (mitigated by small message size)
- Not as efficient as binary protocols

### Alternatives Considered

- **gRPC**: More complex, requires protobuf
- **AMQP**: Overkill for simple heartbeat
- **Binary protocol**: Less debuggable

---

## ADR-003: Authentication Model

**Date**: 2025-01-09  
**Status**: Accepted  
**Deciders**: Project Team, Security Team

### Context

Need to authenticate federation members to prevent unauthorized access.

### Decision

**Mutual TLS (mTLS) with certificate-based authentication**.

### Rationale

1. **Strong Authentication**: Certificate-based identity verification
2. **Standard**: Well-understood and widely implemented
3. **Integration**: Works with existing PKI infrastructure
4. **Security**: TLS 1.3 provides forward secrecy
5. **Scalability**: Scales to large federations

### Certificate Requirements

- **Key Size**: 4096-bit RSA or 256-bit ECC
- **Validity**: 1 year maximum
- **Subject**: CN=site-name, O=federation, C=EU
- **Extensions**: clientAuth and serverAuth EKU

### Consequences

**Positive**:
- Strong security posture
- Integration with EFP CA
- Automatic mutual authentication

**Negative**:
- Certificate management overhead
- Annual rotation required

### Alternatives Considered

- **API Keys**: Weaker, harder to rotate
- **OAuth**: Overkill for machine-to-machine
- **Shared Secrets**: Poor scalability

---

## ADR-004: Heartbeat Interval

**Date**: 2025-01-09  
**Status**: Accepted  
**Deciders**: Project Team

### Context

Need to determine the optimal heartbeat interval balancing responsiveness and overhead.

### Decision

**Default interval: 10 seconds** (configurable 5-60 seconds).

### Rationale

1. **Responsiveness**: 30-second failure detection (3 missed heartbeats)
2. **Overhead**: Minimal network and CPU impact
3. **Flexibility**: Configurable per-site based on needs
4. **Industry Standard**: Similar to other clustering systems

### Calculation

- **Failure Detection**: 3 × interval = 30 seconds
- **Network Overhead**: ~1 KB × 6 per minute = 6 KB/minute per peer
- **CPU Impact**: <1% on modern hardware

### Consequences

**Positive**:
- Fast failure detection
- Low overhead
- Configurable for different environments

**Negative**:
- May need tuning for very large federations
- Network latency variations may cause false positives

### Alternatives Considered

- **5 seconds**: Faster but more overhead
- **30 seconds**: Less overhead but slower detection
- **Adaptive**: More complex, deferred

---

## ADR-005: State Management

**Date**: 2025-01-09  
**Status**: Accepted  
**Deciders**: Project Team

### Context

Need to decide how to manage and persist federation state.

### Decision

**Local state with periodic persistence to disk**.

### Rationale

1. **Simplicity**: No external dependencies
2. **Performance**: Fast local access
3. **Resilience**: Survives network partitions
4. **Recovery**: Can rebuild from peer heartbeats

### State Structure

```python
@dataclass
class PeerState:
    name: str
    status: str  # unknown, healthy, degraded, down
    last_seen: datetime
    metrics: dict
```

### Consequences

**Positive**:
- Simple implementation
- Fast access
- No external dependencies

**Negative**:
- State loss on crash (mitigated by periodic persistence)
- No distributed consensus (acceptable for this use case)

### Alternatives Considered

- **Redis**: External dependency, adds complexity
- **Database**: Overkill for simple state
- **Distributed consensus**: Too complex for current needs

---

## ADR-006: Monitoring Approach

**Date**: 2025-01-09  
**Status**: Accepted  
**Deciders**: Project Team

### Context

Need to choose monitoring and metrics approach.

### Decision

**Prometheus metrics with optional webhook alerting**.

### Rationale

1. **Standardization**: Prometheus is industry standard
2. **Integration**: Works with existing EFP monitoring
3. **Flexibility**: Rich query language for alerting
4. **Ecosystem**: Grafana dashboards, alerting rules

### Metrics

- **Counters**: Heartbeats sent/received
- **Gauges**: Peer status, last seen
- **Histograms**: Latency distributions

### Consequences

**Positive**:
- Standard monitoring approach
- Easy integration
- Rich ecosystem

**Negative**:
- Requires Prometheus infrastructure
- Additional configuration

### Alternatives Considered

- **Custom metrics**: Reinventing the wheel
- **Syslog only**: Limited queryability
- **Grafana Loki**: Good for logs, not metrics

---

## ADR-007: Deployment Model

**Date**: 2025-01-09  
**Status**: Accepted  
**Deciders**: Project Team

### Context

Need to decide on deployment architecture.

### Decision

**Distributed deployment: Each site runs its own daemon**.

### Rationale

1. **Resilience**: No single point of failure
2. **Performance**: Local processing, minimal latency
3. **Autonomy**: Sites can operate independently
4. **Scalability**: Linear scaling with federation size

### Architecture

```
Site A ──┐
         ├── Heartbeat Mesh ──┐
Site B ──┤                    ├── Federation State
         └────────────────────┘
Site C ──┘
```

### Consequences

**Positive**:
- Highly resilient
- Scales well
- Sites have autonomy

**Negative**:
- More deployment effort
- Configuration management across sites

### Alternatives Considered

- **Centralized**: Single point of failure
- **Hybrid**: More complex, not needed yet

---

## ADR-008: Configuration Management

**Date**: 2025-01-09  
**Status**: Accepted  
**Deciders**: Project Team

### Context

Need to decide on configuration approach.

### Decision

**YAML configuration file with sensible defaults**.

### Rationale

1. **Human-Readable**: Easy to understand and edit
2. **Standard**: YAML widely used in operations
3. **Flexible**: Supports complex nested structures
4. **Versionable**: Can be managed in config management systems

### Configuration Structure

```yaml
general:
  log_level: "INFO"

client:
  interval_seconds: 10
  federation:
    peers:
      - name: "lumi-prod"
        endpoint: "https://..."

server:
  listen_port: 8443
  tls:
    enabled: true
```

### Consequences

**Positive**:
- Easy to understand
- Flexible
- Versionable

**Negative**:
- YAML indentation errors
- No schema validation by default

### Alternatives Considered

- **JSON**: Less human-friendly
- **TOML**: Less common
- **Environment variables**: Limited for complex configs

---

## Review Process

These ADRs should be reviewed:
- **Annually**: To ensure they remain valid
- **On major changes**: When new requirements emerge
- **When issues arise**: If decisions cause problems

## Change Process

To change an ADR:
1. Create new ADR document
2. Reference previous ADR
3. Get team approval
4. Update decision status
