"""Shared test fixtures for Slurm Heartbeat."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from slurmheartbeat.client.config import (
    HeartbeatClientConfig,
    PeerConfig,
    ServerConfig,
    TLSConfig,
)
from slurmheartbeat.monitoring.metrics import PrometheusConfig
from slurmheartbeat.protocol.schema import CapacityHint, ReadinessMessage, ReadinessStatus, Signals


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return HeartbeatClientConfig(
        interval_seconds=30,
        timeout_seconds=10,
        retry_count=3,
        retry_backoff=1.0,
        slurm=MagicMock(api_url="http://localhost:6875", api_version="0.0.39", timeout=5),
        federation=MagicMock(peers=[]),
        tls=TLSConfig(
            enabled=True,
            cert_file="/tmp/test-cert.pem",  # noqa: S108
            key_file="/tmp/test-key.pem",  # noqa: S108
            ca_file="/tmp/test-ca.pem",  # noqa: S108
            client_auth="required",
            min_version="1.3",
            max_version="1.3",
        ),
    )


@pytest.fixture
def sample_server_config():
    """Sample server configuration for testing."""
    return ServerConfig(
        enabled=True,
        listen_address="0.0.0.0",
        listen_port=8443,
        tls=TLSConfig(
            enabled=True,
            cert_file="/tmp/test-cert.pem",  # noqa: S108
            key_file="/tmp/test-key.pem",  # noqa: S108
            ca_file="/tmp/test-ca.pem",  # noqa: S108
            client_auth="required",
            min_version="1.3",
            max_version="1.3",
        ),
        max_connections=100,
        connection_timeout=30,
        allowed_sites=["test-site"],
    )


@pytest.fixture
def sample_peer():
    """Sample federation peer for testing."""
    return PeerConfig(
        name="test-peer",
        endpoint="https://test-peer.example.com:8443/heartbeat",
        site="test-site",
    )


@pytest.fixture
def sample_readiness_message():
    """Sample readiness message for testing."""
    return ReadinessMessage(
        schema_version="0.1",
        site_id="test-site",
        cluster_name="test-cluster",
        observed_at="2024-01-01T00:00:00Z",
        status=ReadinessStatus.READY,
        fed_state="ACTIVE",
        reason="scheduler_accepting_work",
        ttl_seconds=90,
        signals=Signals(
            slurmctld_reachable=True,
            slurm_federation_visible=True,
            maintenance=False,
            accepting_new_jobs=True,
            queue_pressure="normal",
            critical_partitions_available=True,
        ),
        capacity_hint=CapacityHint(
            idle_nodes=10,
            down_nodes=0,
            drained_nodes=2,
            pending_jobs=5,
            running_jobs=100,
        ),
    )


@pytest.fixture
def metrics_config():
    """Prometheus metrics configuration for testing."""
    return PrometheusConfig(
        enabled=True,
        port=9090,
        path="/metrics",
        listen_address="0.0.0.0",
    )


@pytest.fixture
def mock_collector():
    """Mock Slurm collector for testing."""
    collector = MagicMock()
    collector.collect = MagicMock(
        return_value=MagicMock(
            cluster_name="test-cluster",
            version="23.11",
            uptime=86400,
        )
    )
    return collector


@pytest.fixture
def mock_sender():
    """Mock heartbeat sender for testing."""
    sender = MagicMock()
    sender.send = MagicMock(return_value=MagicMock(success=True, peer_name="test", latency_ms=10.0))
    return sender


@pytest.fixture
def mock_normalizer():
    """Mock readiness normalizer for testing."""
    normalizer = MagicMock()
    normalizer.normalize = MagicMock(
        return_value=ReadinessMessage(
            schema_version="0.1",
            site_id="test",
            cluster_name="test",
            observed_at="2024-01-01T00:00:00Z",
            status=ReadinessStatus.READY,
            fed_state="ACTIVE",
            reason="scheduler_accepting_work",
            ttl_seconds=90,
            signals=Signals(
                slurmctld_reachable=True,
                slurm_federation_visible=True,
                maintenance=False,
                accepting_new_jobs=True,
                queue_pressure="normal",
                critical_partitions_available=True,
            ),
            capacity_hint=CapacityHint(
                idle_nodes=10,
                down_nodes=0,
                drained_nodes=2,
                pending_jobs=5,
                running_jobs=100,
            ),
        )
    )
    return normalizer


@pytest.fixture
def sample_client_config():
    """Sample client configuration for testing."""
    from slurmheartbeat.client.config import ClientConfig, FederationConfig, SlurmConfig

    config = ClientConfig()
    config.client = HeartbeatClientConfig(
        interval_seconds=30,
        timeout_seconds=10,
        retry_count=3,
        retry_backoff=1.0,
        slurm=SlurmConfig(api_url="http://localhost:6875", api_version="0.0.39", timeout=5),
        federation=FederationConfig(peers=[
            PeerConfig(name="test-peer", endpoint="https://test.example.com:8443", site="test-site")
        ]),
    )
    return config


@pytest.fixture
def sample_prometheus_config():
    """Sample Prometheus configuration for testing."""
    return PrometheusConfig(
        enabled=True,
        port=9090,
        path="/metrics",
        listen_address="0.0.0.0",
    )


@pytest.fixture
def sample_heartbeat_message():
    """Sample heartbeat message for testing."""
    from slurmheartbeat.protocol.message import ClusterInfo, HeartbeatMessage

    return HeartbeatMessage(
        cluster=ClusterInfo(id="test", name="test-cluster", site="test-site"),
    )
