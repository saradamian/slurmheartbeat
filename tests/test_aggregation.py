"""Tests for metrics aggregation component."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from slurmheartbeat.federation.aggregation import FederatedMetrics, MetricsAggregator
from slurmheartbeat.federation.discovery import FederationPeer
from slurmheartbeat.protocol.schema import CapacityHint


class TestFederatedMetrics:
    """Test FederatedMetrics class."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        metrics = FederatedMetrics(
            total_idle_nodes=100,
            total_pending_jobs=50,
            peer_count=5,
            healthy_peer_count=4,
            federation_health="healthy",
        )

        d = metrics.to_dict()

        assert d["total_idle_nodes"] == 100
        assert d["total_pending_jobs"] == 50
        assert d["peer_count"] == 5
        assert d["healthy_peer_count"] == 4
        assert d["federation_health"] == "healthy"
        assert "last_aggregation" in d


class TestMetricsAggregator:
    """Test MetricsAggregator class."""

    @pytest.fixture
    def aggregator(self):
        """Create a MetricsAggregator instance."""
        return MetricsAggregator()

    def test_aggregate_peer_metrics(self, aggregator):
        """Test aggregating metrics from peers."""
        peers = [
            FederationPeer(
                name="peer1",
                endpoint="https://peer1.example.com/readiness",
                site="Site 1",
                capacity_hint=CapacityHint(idle_nodes=10, pending_jobs=5),
                last_seen=datetime.utcnow(),
                consecutive_failures=0,
            ),
            FederationPeer(
                name="peer2",
                endpoint="https://peer2.example.com/readiness",
                site="Site 2",
                capacity_hint=CapacityHint(idle_nodes=20, pending_jobs=10),
                last_seen=datetime.utcnow(),
                consecutive_failures=0,
            ),
        ]

        metrics = aggregator.aggregate_peer_metrics(peers)

        assert metrics.total_idle_nodes == 30
        assert metrics.total_pending_jobs == 15
        assert metrics.peer_count == 2
        assert metrics.healthy_peer_count == 2
        assert metrics.federation_health == "healthy"

    def test_aggregate_with_unhealthy_peers(self, aggregator):
        """Test aggregation excludes unhealthy peers."""
        peers = [
            FederationPeer(
                name="peer1",
                endpoint="https://peer1.example.com/readiness",
                site="Site 1",
                capacity_hint=CapacityHint(idle_nodes=10, pending_jobs=5),
                last_seen=datetime.utcnow(),
                consecutive_failures=0,
            ),
            FederationPeer(
                name="peer2",
                endpoint="https://peer2.example.com/readiness",
                site="Site 2",
                capacity_hint=CapacityHint(idle_nodes=20, pending_jobs=10),
                last_seen=datetime.utcnow() - timedelta(seconds=200),
                consecutive_failures=0,
            ),
        ]

        metrics = aggregator.aggregate_peer_metrics(peers)

        # Only peer1 should be counted
        assert metrics.total_idle_nodes == 10
        assert metrics.healthy_peer_count == 1

    def test_compute_federation_health(self, aggregator):
        """Test federation health calculation."""
        peers = [
            FederationPeer(
                name="peer1",
                endpoint="https://peer1.example.com/readiness",
                site="Site 1",
                last_seen=datetime.utcnow(),
                consecutive_failures=0,
            ),
            FederationPeer(
                name="peer2",
                endpoint="https://peer2.example.com/readiness",
                site="Site 2",
                last_seen=datetime.utcnow(),
                consecutive_failures=0,
            ),
        ]

        health = aggregator.compute_federation_health(peers)
        assert health == "healthy"

    def test_compute_federation_health_no_peers(self, aggregator):
        """Test federation health with no peers."""
        health = aggregator.compute_federation_health([])
        assert health == "no_peers"

    def test_compute_federation_health_degraded(self, aggregator):
        """Test degraded federation health."""
        peers = [
            FederationPeer(
                name="peer1",
                endpoint="https://peer1.example.com/readiness",
                site="Site 1",
                last_seen=datetime.utcnow(),
                consecutive_failures=0,
            ),
            FederationPeer(
                name="peer2",
                endpoint="https://peer2.example.com/readiness",
                site="Site 2",
                last_seen=datetime.utcnow(),
                consecutive_failures=0,
            ),
            FederationPeer(
                name="peer3",
                endpoint="https://peer3.example.com/readiness",
                site="Site 3",
                last_seen=datetime.utcnow() - timedelta(seconds=200),
                consecutive_failures=0,
            ),
        ]

        health = aggregator.compute_federation_health(peers)
        # 2/3 = 67% healthy, which is >= 50% but < 80%, so "degraded"
        assert health == "degraded"

    def test_generate_federation_report(self, aggregator):
        """Test federation report generation."""
        peers = [
            FederationPeer(
                name="peer1",
                endpoint="https://peer1.example.com/readiness",
                site="Site 1",
                capacity_hint=CapacityHint(idle_nodes=10, pending_jobs=5),
                last_seen=datetime.utcnow(),
                consecutive_failures=0,
            ),
        ]

        report = aggregator.generate_federation_report(peers)

        assert "metrics" in report
        assert "statistics" in report
        assert "peers" in report
        assert "generated_at" in report
        assert report["metrics"]["total_idle_nodes"] == 10

    def test_get_historical_trend(self, aggregator):
        """Test historical trend calculation."""
        peers = [
            FederationPeer(
                name="peer1",
                endpoint="https://peer1.example.com/readiness",
                site="Site 1",
                capacity_hint=CapacityHint(idle_nodes=10, pending_jobs=5),
                last_seen=datetime.utcnow(),
                consecutive_failures=0,
            ),
        ]

        # Add some history
        aggregator.aggregate_peer_metrics(peers)
        peers[0].capacity_hint = CapacityHint(idle_nodes=20, pending_jobs=3)
        aggregator.aggregate_peer_metrics(peers)

        trend = aggregator.get_historical_trend("total_idle_nodes")
        assert -1.0 <= trend <= 1.0

    def test_get_metrics_for_prometheus(self, aggregator):
        """Test Prometheus metrics format."""
        peers = [
            FederationPeer(
                name="peer1",
                endpoint="https://peer1.example.com/readiness",
                site="Site 1",
                capacity_hint=CapacityHint(idle_nodes=10, pending_jobs=5),
                last_seen=datetime.utcnow(),
                consecutive_failures=0,
            ),
        ]

        aggregator.aggregate_peer_metrics(peers)
        metrics = aggregator.get_metrics_for_prometheus()

        assert "slurmheartbeat_federation_idle_nodes" in metrics
        assert "slurmheartbeat_federation_pending_jobs" in metrics
        assert "slurmheartbeat_federation_peer_count" in metrics
        assert metrics["slurmheartbeat_federation_idle_nodes"] == 10

    def test_empty_history(self, aggregator):
        """Test aggregation with empty history."""
        metrics = aggregator.get_metrics_for_prometheus()
        assert metrics == {}
