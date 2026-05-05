"""Data normalizer to map Slurm state to EFP readiness schema.

Per EFP recommendation:
- Map local Slurm state to the standardized readiness schema
- Avoid user identifiers, job names, account names, and project metadata
- Produce coarse-grained capacity hints only
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from slurmheartbeat.protocol.schema import (
    CapacityHint,
    QueuePressure,
    ReadinessMessage,
    ReadinessStatus,
    Signals,
)

if TYPE_CHECKING:
    from slurmheartbeat.client.collector import ClusterMetrics

logger = logging.getLogger(__name__)


class ReadinessNormalizer:
    """Normalizes Slurm metrics to EFP readiness schema.

    This class transforms raw Slurm metrics into the EFP-aligned readiness
    message format, applying business logic to determine readiness status
    and signals based on local cluster state.

    Per EFP recommendation:
    - Do not include per-user, per-project, job-name, account, or filesystem information
    - Keep authorization independent from the payload
    - Make the service read-only
    """

    def __init__(
        self,
        site_id: str,
        cluster_name: str,
        fed_state: str = "UNKNOWN",
        ttl_seconds: int = 90,
    ):
        """Initialize the normalizer.

        Args:
            site_id: Unique site identifier (e.g., "lumi", "leonardo")
            cluster_name: Local cluster name (e.g., "lumi-prod")
            fed_state: Federation state from Slurm (e.g., "ACTIVE", "INACTIVE")
            ttl_seconds: Time-to-live for readiness messages
        """
        self.site_id = site_id
        self.cluster_name = cluster_name
        self.fed_state = fed_state
        self.ttl_seconds = ttl_seconds

    def normalize(
        self,
        metrics: ClusterMetrics,
        slurmctld_reachable: bool | None = None,
        maintenance: bool = False,
    ) -> ReadinessMessage:
        """Normalize Slurm metrics to readiness message.

        Args:
            metrics: Collected Slurm metrics
            slurmctld_reachable: Whether slurmctld is reachable. If None, derived from metrics.collect_success
            maintenance: Whether the site is in maintenance mode

        Returns:
            ReadinessMessage aligned with EFP schema
        """
        # Derive slurmctld_reachable from collection success if not explicitly provided
        if slurmctld_reachable is None:
            slurmctld_reachable = metrics.collect_success

        # Determine readiness status based on signals
        status, reason = self._determine_status(metrics, slurmctld_reachable, maintenance)

        # Build signals
        signals = self._build_signals(metrics, slurmctld_reachable, maintenance)

        # Build capacity hint (coarse-grained, no user/job details)
        capacity_hint = self._build_capacity_hint(metrics)

        # Create readiness message
        message = ReadinessMessage(
            site_id=self.site_id,
            cluster_name=self.cluster_name,
            observed_at=datetime.utcnow().isoformat() + "Z",
            schema_version="0.1",
            status=status,
            fed_state=self.fed_state,
            reason=reason,
            ttl_seconds=self.ttl_seconds,
            signals=signals,
            capacity_hint=capacity_hint,
        )

        return message

    def _determine_status(
        self,
        metrics: ClusterMetrics,
        slurmctld_reachable: bool,
        maintenance: bool,
    ) -> tuple[ReadinessStatus, str]:
        """Determine readiness status based on cluster state.

        Per EFP recommendation:
        - ready: site is reachable and intentionally accepting relevant federated work
        - limited: reachable, but degraded capacity, maintenance, high queue pressure, or partial partition availability
        - draining: site is intentionally stopping intake
        - unavailable: site cannot be reached, Slurm is unhealthy, or local policy prevents serving
        - unknown: insufficient information to determine status

        Args:
            metrics: Collected Slurm metrics
            slurmctld_reachable: Whether slurmctld is reachable
            maintenance: Whether the site is in maintenance mode

        Returns:
            Tuple of (status, reason)
        """
        # Check if controller is reachable
        if not slurmctld_reachable:
            return ReadinessStatus.UNAVAILABLE, "slurmctld unreachable"

        # Check maintenance mode
        if maintenance:
            return ReadinessStatus.LIMITED, "maintenance mode"

        # Check node health
        total_nodes = metrics.node_stats.total
        if total_nodes == 0:
            return ReadinessStatus.UNKNOWN, "no nodes detected"

        unhealthy_ratio = (metrics.node_stats.down + metrics.node_stats.drained) / total_nodes
        if unhealthy_ratio > 0.5:
            return ReadinessStatus.UNAVAILABLE, "majority of nodes unhealthy"
        elif unhealthy_ratio > 0.2:
            return ReadinessStatus.LIMITED, "significant node degradation"

        # Check partition availability (only if partitions are provided)
        if metrics.partition_stats:
            partition_available = any(p.total_nodes > 0 for p in metrics.partition_stats)
            if not partition_available:
                return ReadinessStatus.UNAVAILABLE, "no partitions available"
            # Check if any partition has idle nodes
            critical_partitions_available = any(p.idle_nodes > 0 for p in metrics.partition_stats)
            if not critical_partitions_available and metrics.node_stats.idle == 0:
                return ReadinessStatus.LIMITED, "no idle nodes in partitions"

        # Check queue pressure
        queue_pressure = self._determine_queue_pressure(metrics)
        if queue_pressure == QueuePressure.CRITICAL:
            return ReadinessStatus.LIMITED, "critical queue pressure"

        # Check federation state
        if self.fed_state == "INACTIVE":
            return ReadinessStatus.DRAINING, "federation inactive"

        # All checks passed
        return ReadinessStatus.READY, "site ready"

    def _build_signals(
        self,
        metrics: ClusterMetrics,
        slurmctld_reachable: bool,
        maintenance: bool,
    ) -> Signals:
        """Build signals from metrics.

        Args:
            metrics: Collected Slurm metrics
            slurmctld_reachable: Whether slurmctld is reachable
            maintenance: Whether the site is in maintenance mode

        Returns:
            Signals object with current state
        """
        # Determine queue pressure level
        queue_pressure = self._determine_queue_pressure(metrics)

        # Check critical partitions
        critical_partitions_available = self._check_critical_partitions(metrics)

        # Determine if accepting new jobs
        accepting_new_jobs = not maintenance and slurmctld_reachable

        return Signals(
            slurmctld_reachable=slurmctld_reachable,
            slurm_federation_visible=self.fed_state == "ACTIVE",
            maintenance=maintenance,
            accepting_new_jobs=accepting_new_jobs,
            queue_pressure=queue_pressure,
            critical_partitions_available=critical_partitions_available,
        )

    def _build_capacity_hint(self, metrics: ClusterMetrics) -> CapacityHint:
        """Build capacity hint from metrics.

        Per EFP recommendation: Coarse-grained capacity indicators only.
        No user/job/account details.

        Args:
            metrics: Collected Slurm metrics

        Returns:
            CapacityHint with aggregate counts
        """
        return CapacityHint(
            idle_nodes=metrics.node_stats.idle,
            down_nodes=metrics.node_stats.down,
            drained_nodes=metrics.node_stats.drained,
            pending_jobs=metrics.job_stats.pending,
            running_jobs=metrics.job_stats.running,
        )

    def _determine_queue_pressure(self, metrics: ClusterMetrics) -> QueuePressure:
        """Determine queue pressure level from job statistics.

        Args:
            metrics: Collected Slurm metrics

        Returns:
            QueuePressure enum value
        """
        job_stats = metrics.job_stats
        node_stats = metrics.node_stats

        if node_stats.total == 0:
            return QueuePressure.LOW

        # Calculate pending ratio
        total_jobs = job_stats.pending + job_stats.running
        if total_jobs == 0:
            return QueuePressure.LOW

        pending_ratio = job_stats.pending / total_jobs

        # Check absolute pending count
        if job_stats.pending > 1000 or pending_ratio > 0.9:
            return QueuePressure.CRITICAL
        elif job_stats.pending > 500 or pending_ratio > 0.7:
            return QueuePressure.HIGH
        elif job_stats.pending > 100 or pending_ratio > 0.5:
            return QueuePressure.NORMAL
        else:
            return QueuePressure.LOW

    def _check_critical_partitions(self, metrics: ClusterMetrics) -> bool:
        """Check if critical partitions are available.

        This is a simplified check - in production, this would use
        site-specific partition configuration.

        Args:
            metrics: Collected Slurm metrics

        Returns:
            True if at least one partition has available nodes
        """
        for partition in metrics.partition_stats:
            if partition.total_nodes > 0 and partition.idle_nodes > 0:
                return True
        return False

    def _calculate_node_health(self, metrics: ClusterMetrics) -> float:
        """Calculate node health as a ratio.

        Args:
            metrics: Collected Slurm metrics

        Returns:
            Node health ratio (0.0 to 1.0)
        """
        total_nodes = metrics.node_stats.total
        if total_nodes == 0:
            return 0.0

        unhealthy_nodes = metrics.node_stats.down + metrics.node_stats.drained
        return max(0.0, 1.0 - (unhealthy_nodes / total_nodes))
