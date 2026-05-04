"""Heartbeat message protocol definitions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


@dataclass
class ClusterInfo:
    """Information about the local cluster."""

    id: str
    name: str
    site: str
    version: str = "unknown"
    uptime: int = 0


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
class FederationInfo:
    """Federation state information."""

    peers_seen: list[str] = field(default_factory=list)
    peers_unreachable: list[str] = field(default_factory=list)
    federation_name: str = "efp"


@dataclass
class HeartbeatMessage:
    """Heartbeat message sent between federation members.

    DEPRECATION NOTICE:
    This legacy protocol is maintained for backward compatibility with existing
    federation peers. New implementations should use ReadinessMessage from
    slurmheartbeat.protocol.schema for EFP-aligned readiness publishing.

    The legacy HeartbeatMessage:
    - Uses full Slurm metrics (not EFP schema)
    - Supports P2P heartbeat exchange
    - Will be deprecated in a future release

    The EFP ReadinessMessage:
    - Uses minimal readiness schema (status, signals, capacity_hint)
    - Serves /readiness endpoint for pull-based access
    - Recommended for new EFP deployments
    """

    version: str = "1.0"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    cluster: ClusterInfo | None = None
    status: str = "healthy"  # healthy, degraded, unhealthy
    node_stats: NodeStats = field(default_factory=NodeStats)
    partition_stats: list[PartitionStats] = field(default_factory=list)
    job_stats: JobStats = field(default_factory=JobStats)
    resource_usage: ResourceUsage = field(default_factory=ResourceUsage)
    federation: FederationInfo | None = None
    signature: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "cluster": {
                "id": self.cluster.id,
                "name": self.cluster.name,
                "site": self.cluster.site,
                "version": self.cluster.version,
                "uptime": self.cluster.uptime,
            }
            if self.cluster
            else None,
            "status": self.status,
            "node_stats": {
                "total": self.node_stats.total,
                "idle": self.node_stats.idle,
                "allocated": self.node_stats.allocated,
                "drained": self.node_stats.drained,
                "down": self.node_stats.down,
            },
            "partition_stats": [
                {
                    "name": p.name,
                    "total_cpus": p.total_cpus,
                    "available_cpus": p.available_cpus,
                    "total_nodes": p.total_nodes,
                    "idle_nodes": p.idle_nodes,
                    "pending_jobs": p.pending_jobs,
                    "running_jobs": p.running_jobs,
                }
                for p in self.partition_stats
            ],
            "job_stats": {
                "pending": self.job_stats.pending,
                "running": self.job_stats.running,
                "completed": self.job_stats.completed,
                "failed": self.job_stats.failed,
                "cancelled": self.job_stats.cancelled,
            },
            "resource_usage": {
                "cpu_percent": self.resource_usage.cpu_percent,
                "memory_percent": self.resource_usage.memory_percent,
                "gpu_percent": self.resource_usage.gpu_percent,
            },
            "federation": {
                "peers_seen": self.federation.peers_seen if self.federation else [],
                "peers_unreachable": self.federation.peers_unreachable if self.federation else [],
                "federation_name": self.federation.federation_name if self.federation else "efp",
            }
            if self.federation
            else None,
            "signature": self.signature,
        }

    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HeartbeatMessage:
        """Create message from dictionary."""
        cluster_data = data.get("cluster")
        cluster = (
            ClusterInfo(
                id=cluster_data["id"],
                name=cluster_data["name"],
                site=cluster_data["site"],
                version=cluster_data.get("version", "unknown"),
                uptime=cluster_data.get("uptime", 0),
            )
            if cluster_data
            else None
        )

        node_stats_data = data.get("node_stats", {})
        node_stats = NodeStats(
            total=node_stats_data.get("total", 0),
            idle=node_stats_data.get("idle", 0),
            allocated=node_stats_data.get("allocated", 0),
            drained=node_stats_data.get("drained", 0),
            down=node_stats_data.get("down", 0),
        )

        partition_stats = []
        for p in data.get("partition_stats", []):
            partition_stats.append(
                PartitionStats(
                    name=p.get("name", "unknown"),
                    total_cpus=p.get("total_cpus", 0),
                    available_cpus=p.get("available_cpus", 0),
                    total_nodes=p.get("total_nodes", 0),
                    idle_nodes=p.get("idle_nodes", 0),
                    pending_jobs=p.get("pending_jobs", 0),
                    running_jobs=p.get("running_jobs", 0),
                )
            )

        job_stats_data = data.get("job_stats", {})
        job_stats = JobStats(
            pending=job_stats_data.get("pending", 0),
            running=job_stats_data.get("running", 0),
            completed=job_stats_data.get("completed", 0),
            failed=job_stats_data.get("failed", 0),
            cancelled=job_stats_data.get("cancelled", 0),
        )

        resource_usage_data = data.get("resource_usage", {})
        resource_usage = ResourceUsage(
            cpu_percent=resource_usage_data.get("cpu_percent", 0.0),
            memory_percent=resource_usage_data.get("memory_percent", 0.0),
            gpu_percent=resource_usage_data.get("gpu_percent", 0.0),
        )

        federation_data = data.get("federation")
        federation = (
            FederationInfo(
                peers_seen=federation_data.get("peers_seen", []),
                peers_unreachable=federation_data.get("peers_unreachable", []),
                federation_name=federation_data.get("federation_name", "efp"),
            )
            if federation_data
            else None
        )

        return cls(
            version=data.get("version", "1.0"),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
            cluster=cluster,
            status=data.get("status", "healthy"),
            node_stats=node_stats,
            partition_stats=partition_stats,
            job_stats=job_stats,
            resource_usage=resource_usage,
            federation=federation,
            signature=data.get("signature"),
        )

    @classmethod
    def from_metrics(cls, metrics: Any, cluster_info: ClusterInfo) -> HeartbeatMessage:
        """Create heartbeat message from collected metrics."""
        return cls(
            cluster=cluster_info,
            status="healthy",
            node_stats=metrics.node_stats,
            partition_stats=metrics.partition_stats,
            job_stats=metrics.job_stats,
            resource_usage=metrics.resource_usage,
        )

    def sign(self, private_key: rsa.RSAPrivateKey | bytes) -> None:
        """Sign the message with a private key.

        Args:
            private_key: Private key (either RSAPrivateKey object or PEM bytes).
        """
        message_json = self.to_json()

        # Handle both key objects and PEM bytes
        if isinstance(private_key, bytes):
            private_key_obj = serialization.load_pem_private_key(
                private_key,
                password=None,
            )
        else:
            private_key_obj = private_key

        signature = private_key_obj.sign(message_json.encode(), padding.PKCS1v15(), hashes.SHA256())
        self.signature = signature.hex()

    def verify_signature(self, public_key_pem: bytes) -> bool:
        """Verify the message signature.

        Args:
            public_key_pem: Public key in PEM format (bytes).

        Returns:
            True if signature is valid, False otherwise.
        """
        if not self.signature:
            return False

        try:
            public_key = serialization.load_pem_public_key(public_key_pem)
            signature_bytes = bytes.fromhex(self.signature)

            # Remove signature for verification
            original_signature = self.signature
            self.signature = None

            try:
                message_json = self.to_json()
                public_key.verify(
                    signature_bytes, message_json.encode(), padding.PKCS1v15(), hashes.SHA256()
                )
                return True
            finally:
                self.signature = original_signature
        except Exception:
            return False

    def get_status(self) -> str:
        """Get overall cluster status."""
        if self.node_stats.down > 0 or self.node_stats.drained > self.node_stats.total * 0.5:
            return "unhealthy"
        elif self.node_stats.drained > 0 or self.node_stats.down > 0:
            return "degraded"
        return "healthy"

    def update_status(self) -> None:
        """Update status based on current metrics."""
        self.status = self.get_status()


__all__ = [
    "ClusterInfo",
    "FederationInfo",
    "HeartbeatMessage",
    "JobStats",
    "NodeStats",
    "PartitionStats",
    "ResourceUsage",
]
