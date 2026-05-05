"""Prometheus metrics exporter for heartbeat daemon."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

logger = logging.getLogger(__name__)


@dataclass
class PrometheusConfig:
    """Prometheus configuration."""

    enabled: bool = True
    port: int = 9090
    path: str = "/metrics"
    listen_address: str = "0.0.0.0"


class MetricsServer:
    """Prometheus metrics server for heartbeat daemon.

    Uses singleton pattern to avoid duplicate metric registration.
    """

    _instance: MetricsServer | None = None
    _metrics_initialized: bool = False

    def __new__(cls, config: PrometheusConfig | None = None) -> MetricsServer:
        """Singleton pattern - return existing instance if available."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: PrometheusConfig | None = None):
        """Initialize metrics server.

        Args:
            config: Prometheus configuration. If None, uses defaults.
        """
        # Only initialize once
        if MetricsServer._metrics_initialized:
            return

        # Use defaults if config not provided
        self.config = config or PrometheusConfig()
        self._running = False

        # Use a custom registry for testing
        self._registry = CollectorRegistry()

        # Only register metrics if enabled
        if not self.config.enabled:
            return

        # Define metrics
        # Counters
        self.heartbeat_sent = Counter(
            "slurmheartbeat_sent_total",
            "Total heartbeats sent",
            ["site"],
            registry=self._registry,
        )
        self.heartbeat_received = Counter(
            "slurmheartbeat_received_total",
            "Total heartbeats received",
            ["site"],
            registry=self._registry,
        )
        self.heartbeat_errors = Counter(
            "slurmheartbeat_errors_total",
            "Total heartbeat errors",
            ["site", "error_type"],
            registry=self._registry,
        )

        # Histograms
        self.heartbeat_latency = Histogram(
            "slurmheartbeat_latency_seconds",
            "Heartbeat latency in seconds",
            ["site"],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
            registry=self._registry,
        )

        # Gauges
        self.peer_status = Gauge(
            "slurmheartbeat_member_status",
            "Peer status (1=healthy, 0=degraded, -1=unhealthy)",
            ["site"],
            registry=self._registry,
        )
        self.peer_last_seen = Gauge(
            "slurmheartbeat_member_last_seen_seconds",
            "Seconds since last heartbeat from peer",
            ["site"],
            registry=self._registry,
        )
        self.peer_consecutive_failures = Gauge(
            "slurmheartbeat_member_consecutive_failures",
            "Number of consecutive heartbeat failures",
            ["site"],
            registry=self._registry,
        )

        # Local cluster metrics
        self.local_node_total = Gauge(
            "slurmheartbeat_local_nodes_total",
            "Total nodes in local cluster",
            registry=self._registry,
        )
        self.local_node_idle = Gauge(
            "slurmheartbeat_local_nodes_idle",
            "Idle nodes in local cluster",
            registry=self._registry,
        )
        self.local_node_allocated = Gauge(
            "slurmheartbeat_local_nodes_allocated",
            "Allocated nodes in local cluster",
            registry=self._registry,
        )
        self.local_node_drained = Gauge(
            "slurmheartbeat_local_nodes_drained",
            "Drained nodes in local cluster",
            registry=self._registry,
        )
        self.local_node_down = Gauge(
            "slurmheartbeat_local_nodes_down",
            "Down nodes in local cluster",
            registry=self._registry,
        )

        self.local_jobs_pending = Gauge(
            "slurmheartbeat_local_jobs_pending",
            "Pending jobs in local cluster",
            registry=self._registry,
        )
        self.local_jobs_running = Gauge(
            "slurmheartbeat_local_jobs_running",
            "Running jobs in local cluster",
            registry=self._registry,
        )
        self.local_jobs_failed = Gauge(
            "slurmheartbeat_local_jobs_failed",
            "Failed jobs in local cluster",
            registry=self._registry,
        )

        self.local_cpu_percent = Gauge(
            "slurmheartbeat_local_cpu_percent",
            "CPU usage percentage in local cluster",
            registry=self._registry,
        )
        self.local_memory_percent = Gauge(
            "slurmheartbeat_local_memory_percent",
            "Memory usage percentage in local cluster",
            registry=self._registry,
        )
        self.local_gpu_percent = Gauge(
            "slurmheartbeat_local_gpu_percent",
            "GPU usage percentage in local cluster",
            registry=self._registry,
        )

        MetricsServer._metrics_initialized = True

    async def start(self) -> None:
        """Start the metrics server."""
        if not self.config.enabled:
            logger.info("Prometheus metrics disabled")
            return

        # Idempotence guard - prevent double-start
        if self._running:
            logger.warning("Metrics server already running, skipping start")
            return

        # Only start HTTP server if not already started by publisher
        # Publisher's /metrics endpoint serves the same registry
        logger.info(
            f"Prometheus metrics available at {self.config.listen_address}:{self.config.port}"
        )
        self._running = True

    async def stop(self) -> None:
        """Stop the metrics server."""
        if not self._running:
            return

        logger.info("Stopping Prometheus metrics server")
        self._running = False
        # Note: prometheus_client doesn't provide a clean shutdown method
        # The server will be cleaned up when the process exits

    def record_heartbeat_sent(self, site: str) -> None:
        """Record a heartbeat sent to a site.

        Args:
            site: Site name.
        """
        self.heartbeat_sent.labels(site=site).inc()

    def record_heartbeat_received(self, site: str) -> None:
        """Record a heartbeat received from a site.

        Args:
            site: Site name.
        """
        self.heartbeat_received.labels(site=site).inc()

    def record_heartbeat_error(self, site: str, error_type: str) -> None:
        """Record a heartbeat error.

        Args:
            site: Site name.
            error_type: Type of error (timeout, connection, etc.).
        """
        self.heartbeat_errors.labels(site=site, error_type=error_type).inc()

    def record_heartbeat_latency(self, site: str, latency_seconds: float) -> None:
        """Record heartbeat latency.

        Args:
            site: Site name.
            latency_seconds: Latency in seconds.
        """
        self.heartbeat_latency.labels(site=site).observe(latency_seconds)

    def update_peer_status(
        self, site: str, status: str, last_seen_seconds: float, failures: int
    ) -> None:
        """Update peer status metrics.

        Args:
            site: Site name.
            status: Peer status (healthy, degraded, unhealthy).
            last_seen_seconds: Seconds since last heartbeat.
            failures: Number of consecutive failures.
        """
        # Map status to numeric value
        status_map = {"healthy": 1, "degraded": 0, "unhealthy": -1, "unknown": 0}
        self.peer_status.labels(site=site).set(status_map.get(status, 0))
        self.peer_last_seen.labels(site=site).set(last_seen_seconds)
        self.peer_consecutive_failures.labels(site=site).set(failures)

    def update_local_metrics(
        self,
        node_total: int,
        node_idle: int,
        node_allocated: int,
        node_drained: int,
        node_down: int,
        jobs_pending: int,
        jobs_running: int,
        jobs_failed: int,
        cpu_percent: float,
        memory_percent: float,
        gpu_percent: float,
    ) -> None:
        """Update local cluster metrics.

        Args:
            node_total: Total nodes.
            node_idle: Idle nodes.
            node_allocated: Allocated nodes.
            node_drained: Drained nodes.
            node_down: Down nodes.
            jobs_pending: Pending jobs.
            jobs_running: Running jobs.
            jobs_failed: Failed jobs.
            cpu_percent: CPU usage percentage.
            memory_percent: Memory usage percentage.
            gpu_percent: GPU usage percentage.
        """
        self.local_node_total.set(node_total)
        self.local_node_idle.set(node_idle)
        self.local_node_allocated.set(node_allocated)
        self.local_node_drained.set(node_drained)
        self.local_node_down.set(node_down)

        self.local_jobs_pending.set(jobs_pending)
        self.local_jobs_running.set(jobs_running)
        self.local_jobs_failed.set(jobs_failed)

        self.local_cpu_percent.set(cpu_percent)
        self.local_memory_percent.set(memory_percent)
        self.local_gpu_percent.set(gpu_percent)

    def get_metrics(self) -> str:
        """Get the metrics as Prometheus text format.

        Returns:
            Prometheus-compatible metrics text.
        """
        from prometheus_client import generate_latest

        return generate_latest(self._registry).decode()

    def record_readiness_update(self, status: str, site: str) -> None:
        """Record a readiness update event.

        Args:
            status: Readiness status (ready, limited, draining, unavailable).
            site: Site name.
        """
        # Map readiness status to numeric value for metrics
        status_map = {
            "ready": 1,
            "limited": 0,
            "draining": -1,
            "unavailable": -2,
            "unknown": 0,
        }
        self.peer_status.labels(site=site).set(status_map.get(status, 0))


__all__ = ["MetricsServer", "PrometheusConfig"]
