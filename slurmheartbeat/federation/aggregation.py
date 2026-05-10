"""Monitoring aggregation component for federated metrics.

This module provides metrics aggregation across federation peers for the EuroHPC Federation Platform.

Features:
- Metric aggregation across multiple peers
- Federation health calculation
- Report generation for Prometheus/Grafana dashboards
- Support for both real-time and historical aggregation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from slurmheartbeat.federation.discovery import FederationPeer

logger = logging.getLogger(__name__)


@dataclass
class FederatedMetrics:
    """Aggregated metrics across federation."""

    total_idle_nodes: int = 0
    total_allocated_nodes: int = 0
    total_drained_nodes: int = 0
    total_down_nodes: int = 0
    total_pending_jobs: int = 0
    total_running_jobs: int = 0
    peer_count: int = 0
    healthy_peer_count: int = 0
    federation_health: str = "unknown"
    last_aggregation: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_idle_nodes": self.total_idle_nodes,
            "total_allocated_nodes": self.total_allocated_nodes,
            "total_drained_nodes": self.total_drained_nodes,
            "total_down_nodes": self.total_down_nodes,
            "total_pending_jobs": self.total_pending_jobs,
            "total_running_jobs": self.total_running_jobs,
            "peer_count": self.peer_count,
            "healthy_peer_count": self.healthy_peer_count,
            "federation_health": self.federation_health,
            "last_aggregation": self.last_aggregation.isoformat() if self.last_aggregation else None,
        }


class MetricsAggregator:
    """Aggregates metrics across federation peers."""

    def __init__(self, config: Any | None = None):
        """Initialize metrics aggregator.

        Args:
            config: Optional configuration for aggregation parameters.
        """
        self.config = config or {}
        self._history: list[FederatedMetrics] = []
        self._max_history_size = self.config.get("max_history_size", 100)

    def aggregate_peer_metrics(self, peers: list[FederationPeer]) -> FederatedMetrics:
        """Aggregate metrics from multiple peers.

        Args:
            peers: List of federation peers with capacity hints.

        Returns:
            Aggregated FederatedMetrics.
        """
        total_idle = 0
        total_drained = 0
        total_down = 0
        total_pending = 0
        total_running = 0
        healthy_count = 0

        for peer in peers:
            if peer.is_healthy():
                healthy_count += 1
                total_idle += peer.capacity_hint.idle_nodes
                total_drained += peer.capacity_hint.drained_nodes
                total_down += peer.capacity_hint.down_nodes
                total_pending += peer.capacity_hint.pending_jobs
                total_running += peer.capacity_hint.running_jobs

        # Calculate federation health
        if len(peers) == 0:
            health = "no_peers"
        elif healthy_count == 0:
            health = "unhealthy"
        elif healthy_count >= len(peers) * 0.8:
            health = "healthy"
        elif healthy_count >= len(peers) * 0.5:
            health = "degraded"
        else:
            health = "critical"

        metrics = FederatedMetrics(
            total_idle_nodes=total_idle,
            total_allocated_nodes=0,  # Not available from readiness messages
            total_drained_nodes=total_drained,
            total_down_nodes=total_down,
            total_pending_jobs=total_pending,
            total_running_jobs=total_running,
            peer_count=len(peers),
            healthy_peer_count=healthy_count,
            federation_health=health,
            last_aggregation=datetime.utcnow(),
        )

        # Store in history
        self._history.append(metrics)
        if len(self._history) > self._max_history_size:
            self._history = self._history[-self._max_history_size :]

        return metrics

    def compute_federation_health(self, peers: list[FederationPeer]) -> str:
        """Compute overall federation health.

        Args:
            peers: List of federation peers.

        Returns:
            Health status string.
        """
        if not peers:
            return "no_peers"

        healthy_count = sum(1 for p in peers if p.is_healthy())
        total_count = len(peers)

        if healthy_count == 0:
            return "unhealthy"
        elif healthy_count >= total_count * 0.8:
            return "healthy"
        elif healthy_count >= total_count * 0.5:
            return "degraded"
        else:
            return "critical"

    def generate_federation_report(self, peers: list[FederationPeer]) -> dict[str, Any]:
        """Generate summary report for dashboards.

        Args:
            peers: List of federation peers.

        Returns:
            Dictionary with federation summary.
        """
        metrics = self.aggregate_peer_metrics(peers)

        # Calculate additional statistics
        total_nodes = metrics.total_idle_nodes + metrics.total_drained_nodes + metrics.total_down_nodes
        utilization = 0.0
        if total_nodes > 0:
            # Simple utilization estimate (not accurate without allocated nodes)
            utilization = 1.0 - (metrics.total_idle_nodes / total_nodes)

        pending_ratio = 0.0
        total_jobs = metrics.total_pending_jobs + metrics.total_running_jobs
        if total_jobs > 0:
            pending_ratio = metrics.total_pending_jobs / total_jobs

        return {
            "metrics": metrics.to_dict(),
            "statistics": {
                "total_nodes": total_nodes,
                "utilization_estimate": utilization,
                "pending_job_ratio": pending_ratio,
                "avg_idle_per_peer": metrics.total_idle_nodes / max(metrics.healthy_peer_count, 1),
            },
            "peers": [
                {
                    "name": p.name,
                    "site": p.site,
                    "status": p.status.value,
                    "idle_nodes": p.capacity_hint.idle_nodes,
                    "last_seen": p.last_seen.isoformat() if p.last_seen else None,
                    "healthy": p.is_healthy(),
                }
                for p in peers
            ],
            "generated_at": datetime.utcnow().isoformat(),
        }

    def get_historical_trend(self, metric_name: str, window_size: int = 10) -> float:
        """Get historical trend for a metric.

        Args:
            metric_name: Name of metric to analyze.
            window_size: Number of history entries to consider.

        Returns:
            Trend value (-1.0 to 1.0, negative = decreasing, positive = increasing).
        """
        if len(self._history) < 2:
            return 0.0

        # Get recent history
        recent = self._history[-window_size:] if window_size > 0 else self._history

        # Get metric values
        values = []
        for m in recent:
            value = getattr(m, metric_name, None)
            if value is not None:
                values.append(value)

        if len(values) < 2:
            return 0.0

        # Calculate trend using simple linear regression
        n = len(values)
        x_mean = sum(range(n)) / n
        y_mean = sum(values) / n

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        slope = numerator / denominator

        # Normalize to -1.0 to 1.0 range
        max_slope = max(values) - min(values) if max(values) != min(values) else 1.0
        normalized_slope = slope / max_slope if max_slope > 0 else 0.0

        return max(min(normalized_slope, 1.0), -1.0)

    def get_metrics_for_prometheus(self) -> dict[str, float]:
        """Get metrics in Prometheus format.

        Returns:
            Dictionary of metric names to values.
        """
        if not self._history:
            return {}

        latest = self._history[-1]

        return {
            "slurmheartbeat_federation_idle_nodes": float(latest.total_idle_nodes),
            "slurmheartbeat_federation_drained_nodes": float(latest.total_drained_nodes),
            "slurmheartbeat_federation_down_nodes": float(latest.total_down_nodes),
            "slurmheartbeat_federation_pending_jobs": float(latest.total_pending_jobs),
            "slurmheartbeat_federation_running_jobs": float(latest.total_running_jobs),
            "slurmheartbeat_federation_peer_count": float(latest.peer_count),
            "slurmheartbeat_federation_healthy_peers": float(latest.healthy_peer_count),
            "slurmheartbeat_federation_health": float(
                {"healthy": 1.0, "degraded": 0.5, "critical": 0.0, "unhealthy": 0.0, "no_peers": -1.0}.get(
                    latest.federation_health, 0.0
                )
            ),
        }
