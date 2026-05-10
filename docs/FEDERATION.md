# Federated Capacity Discovery and Monitoring

This document describes the federation components for Slurm Heartbeat, which enable EuroHPC Federation Platform (EFP) integration through peer discovery, capacity aggregation, and queue prediction.

## Overview

The federation components provide three main capabilities:

1. **Federated Capacity Discovery** - Discover and fetch capacity hints from federation peers
2. **Queue Prediction** - Predict queue pressure and wait times based on historical patterns
3. **Metrics Aggregation** - Aggregate metrics across multiple federation peers

## Components

### 1. Federation Discovery (`slurmheartbeat/federation/discovery.py`)

The `FederationDiscovery` class manages peer discovery and capacity fetching:

**Key Features:**
- Peer discovery from configuration
- Health checking of federation peers
- Capacity hint fetching with timeout handling
- Support for pull-based model (EFP-aligned)

**Usage:**
```python
from slurmheartbeat.federation.discovery import FederationDiscovery

# Initialize with configuration
discovery = FederationDiscovery(config)

# Discover peers from config
peers = await discovery.discover_peers()

# Fetch capacity from a specific peer
capacity = await discovery.fetch_peer_capacity(peer, timeout=30)

# Fetch from all peers in parallel
results = await discovery.fetch_all_peers(timeout=30)

# Get federation summary
summary = discovery.get_federation_summary()
```

**Configuration:**
```yaml
client:
  federation:
    enabled: true
    peers:
      - name: "leonardo"
        endpoint: "https://leonardo.example.com:8443/readiness"
        site: "CINECA Italy"
        timeout_seconds: 30
    aggregation_interval_seconds: 60
    peer_timeout_seconds: 30
    max_history_size: 100
```

### 2. Queue Prediction (`slurmheartbeat/federation/prediction.py`)

The `QueuePredictor` class provides queue pressure prediction and wait time estimation:

**Key Features:**
- Queue pressure prediction based on pending/running ratios
- Wait time estimation based on historical patterns
- Trend calculation from time-series data
- Simple heuristics (extensible for ML-based prediction)

**Usage:**
```python
from slurmheartbeat.federation.prediction import QueuePredictor
from slurmheartbeat.protocol.schema import CapacityHint

predictor = QueuePredictor()

# Predict queue pressure
capacity = CapacityHint(idle_nodes=50, pending_jobs=25, running_jobs=20)
pressure = predictor.predict_queue_pressure(capacity)

# Estimate wait time
wait_time = predictor.estimate_wait_time(capacity, pressure)

# Full prediction with trend
history = [
    CapacityHint(idle_nodes=60, pending_jobs=20, running_jobs=15),
    CapacityHint(idle_nodes=55, pending_jobs=22, running_jobs=18),
    CapacityHint(idle_nodes=50, pending_jobs=25, running_jobs=20),
]
prediction = predictor.predict(capacity, history)

print(f"Pressure: {prediction.pressure_level}")
print(f"Wait time: {prediction.predicted_wait_time}")
print(f"Trend: {prediction.pressure_trend}")
print(f"Confidence: {prediction.confidence}")
```

**Prediction Parameters:**
```python
predictor = QueuePredictor({
    "base_wait_time_seconds": 3600,  # 1 hour base
    "high_pressure_threshold": 0.7,
    "critical_pressure_threshold": 0.9,
    "history_window_minutes": 60,
})
```

### 3. Metrics Aggregation (`slurmheartbeat/federation/aggregation.py`)

The `MetricsAggregator` class aggregates metrics across federation peers:

**Key Features:**
- Metric aggregation across multiple peers
- Federation health calculation
- Report generation for Prometheus/Grafana dashboards
- Historical trend analysis

**Usage:**
```python
from slurmheartbeat.federation.aggregation import MetricsAggregator

aggregator = MetricsAggregator()

# Aggregate metrics from peers
metrics = aggregator.aggregate_peer_metrics(peers)

# Generate federation report
report = aggregator.generate_federation_report(peers)

# Get Prometheus metrics
prometheus_metrics = aggregator.get_metrics_for_prometheus()

# Get historical trend
trend = aggregator.get_historical_trend("total_idle_nodes", window_size=10)
```

**Prometheus Metrics:**
```python
# slurmheartbeat_federation_idle_nodes: 100
# slurmheartbeat_federation_drained_nodes: 5
# slurmheartbeat_federation_down_nodes: 2
# slurmheartbeat_federation_pending_jobs: 50
# slurmheartbeat_federation_running_jobs: 30
# slurmheartbeat_federation_peer_count: 5
# slurmheartbeat_federation_healthy_peers: 4
# slurmheartbeat_federation_health: 1.0  # healthy=1.0, degraded=0.5, critical=0.0
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Federation Layer                          │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Discovery    │  │ Prediction   │  │ Aggregation  │      │
│  │ - Peer list  │  │ - Pressure   │  │ - Metrics    │      │
│  │ - Health     │  │ - Wait time  │  │ - Health     │      │
│  │ - Fetching   │  │ - Trend      │  │ - Reports    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    EFP Readiness Publisher                   │
│  /readiness endpoint (pull-based, signed, TTL-based)        │
└─────────────────────────────────────────────────────────────┘
```

## Design Principles

1. **Pull-based preferred** - Use ReadinessMessage (EFP-aligned) for new deployments
2. **Push-based fallback** - Maintain legacy HeartbeatMessage receiver for backward compatibility
3. **Simple heuristics first** - Queue prediction uses basic ratios initially, can be enhanced with ML later
4. **Config-driven federation** - Peer list in config file, with optional service discovery
5. **Timeout handling** - All peer communication has configurable timeouts
6. **Graceful degradation** - If peer unavailable, exclude from aggregation without failing entire system

## EFP Alignment

The federation components align with the EFP recommendation:

- ✅ **Coarse-grained signals only** - No user/job/account details
- ✅ **Cryptographic signing** - RSA-PKCS1v15 signature support
- ✅ **TTL-based freshness** - 90-second default TTL
- ✅ **mTLS authentication** - TLS 1.3 with client certificates
- ✅ **Read-only operation** - No Slurm state modification
- ✅ **Authorization independent from signature** - Separate from signature verification

## Limitations

1. **Unproven at scale** - No production deployments yet
2. **Value tied to EFP adoption** - Market risk as EFP is new (April 2026)
3. **Consumption pattern undecided** - EFP-wide decision on signal consumption
4. **Identity system undecided** - EFP PKI vs. site vs. MyAccessID

## Future Work

- [ ] ML-based queue prediction (LSTM, Prophet, etc.)
- [ ] Service discovery integration (DNS, mDNS, external registry)
- [ ] Real-time peer health monitoring
- [ ] Federated learning for cross-site prediction
- [ ] EFP identity system integration

## Testing

Run federation tests:
```bash
pytest tests/test_federation.py -v
pytest tests/test_prediction.py -v
pytest tests/test_aggregation.py -v
```

## References

- [EFP Recommendation](EFP_HEARTBEAT_RECOMMENDATION.md)
- [EuroHPC Federation Platform](https://www.eurohpc-ju.europa.eu/supercomputers/eurohpc-federation-platform_en)
- [Prometheus Federation](https://prometheus.io/docs/prometheus/latest/federation/)
