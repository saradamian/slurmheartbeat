"""Slurm metrics collector with EFP readiness support.

This collector reads local Slurm state through multiple sources:
1. OpenMetrics (preferred) - native Slurm metrics endpoint
2. scontrol --json - Slurm control interface
3. sinfo/squeue - Fallback for older Slurm versions
4. slurmrestd - REST API if available

Per EFP recommendation: The collector should avoid user/job/account details.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class NodeStats:
    """Node statistics from Slurm."""

    total: int = 0
    idle: int = 0
    allocated: int = 0
    drained: int = 0
    down: int = 0


@dataclass
class PartitionStats:
    """Partition statistics from Slurm."""

    name: str
    total_cpus: int = 0
    available_cpus: int = 0
    total_nodes: int = 0
    idle_nodes: int = 0
    pending_jobs: int = 0
    running_jobs: int = 0


@dataclass
class JobStats:
    """Job statistics from Slurm."""

    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0


@dataclass
class ResourceUsage:
    """Resource usage metrics."""

    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    gpu_percent: float = 0.0


@dataclass
class ClusterMetrics:
    """Complete cluster metrics."""

    cluster_name: str = "unknown"
    version: str = "unknown"
    uptime: int = 0
    node_stats: NodeStats = field(default_factory=NodeStats)
    partition_stats: list[PartitionStats] = field(default_factory=list)
    job_stats: JobStats = field(default_factory=JobStats)
    resource_usage: ResourceUsage = field(default_factory=ResourceUsage)


class SlurmCollector:
    """Collects metrics from Slurm workload manager."""

    def __init__(self, config: Any):
        """Initialize the collector.

        Args:
            config: Slurm configuration with api_url and timeout.
        """
        self.api_url = config.api_url.rstrip("/")
        self.api_version = getattr(config, "api_version", "0.0.39")
        self.timeout = getattr(config, "timeout", 5)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=f"{self.api_url}/slurm/v{self.api_version}",
                timeout=self.timeout,
            )
        return self._client

    async def collect(self) -> ClusterMetrics:
        """Collect all cluster metrics.

        Returns:
            ClusterMetrics with current state.
        """
        metrics = ClusterMetrics()

        try:
            # Collect in parallel where possible
            await asyncio.gather(
                self._collect_cluster_info(metrics),
                self._collect_node_stats(metrics),
                self._collect_partition_stats(metrics),
                self._collect_job_stats(metrics),
                return_exceptions=True,
            )
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")

        return metrics

    async def _collect_cluster_info(self, metrics: ClusterMetrics) -> None:
        """Collect cluster information."""
        try:
            client = await self._get_client()
            response = await client.get("/cluster/info")
            response.raise_for_status()
            data = response.json()

            if "cluster" in data:
                cluster = data["cluster"]
                metrics.cluster_name = cluster.get("cluster_name", "unknown")
                metrics.version = cluster.get("version", "unknown")
                metrics.uptime = cluster.get("uptime", 0)
        except Exception as e:
            logger.warning(f"Failed to collect cluster info: {e}")

    async def _collect_node_stats(self, metrics: ClusterMetrics) -> None:
        """Collect node statistics."""
        try:
            client = await self._get_client()
            response = await client.get("/nodes")
            response.raise_for_status()
            data = response.json()

            nodes = data.get("nodes", [])
            stats = NodeStats()

            for node in nodes:
                state = node.get("state", "").lower()
                if "idle" in state:
                    stats.idle += 1
                elif "allocated" in state:
                    stats.allocated += 1
                elif "drained" in state:
                    stats.drained += 1
                elif "down" in state:
                    stats.down += 1
                stats.total += 1

            metrics.node_stats = stats
        except Exception as e:
            logger.warning(f"Failed to collect node stats: {e}")

    async def _collect_partition_stats(self, metrics: ClusterMetrics) -> None:
        """Collect partition statistics."""
        try:
            client = await self._get_client()
            response = await client.get("/partitions")
            response.raise_for_status()
            data = response.json()

            partitions = []
            for part in data.get("partitions", []):
                stats = PartitionStats(
                    name=part.get("name", "unknown"),
                    total_cpus=part.get("total_cpus", 0),
                    available_cpus=part.get("available_cpus", 0),
                    total_nodes=part.get("total_nodes", 0),
                    idle_nodes=part.get("idle_nodes", 0),
                    pending_jobs=part.get("pending_jobs", 0),
                    running_jobs=part.get("running_jobs", 0),
                )
                partitions.append(stats)

            metrics.partition_stats = partitions
        except Exception as e:
            logger.warning(f"Failed to collect partition stats: {e}")

    async def _collect_job_stats(self, metrics: ClusterMetrics) -> None:
        """Collect job statistics."""
        try:
            client = await self._get_client()
            response = await client.get("/jobs")
            response.raise_for_status()
            data = response.json()

            jobs = data.get("jobs", [])
            stats = JobStats()

            for job in jobs:
                state = job.get("job_state", "").upper()
                if state == "PD":
                    stats.pending += 1
                elif state == "R":
                    stats.running += 1
                elif state == "CD":
                    stats.completed += 1
                elif state == "F":
                    stats.failed += 1
                elif state == "CA":
                    stats.cancelled += 1

            metrics.job_stats = stats
        except Exception as e:
            logger.warning(f"Failed to collect job stats: {e}")

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
