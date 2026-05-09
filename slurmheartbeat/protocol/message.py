"""Heartbeat message protocol definitions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


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

    state: str = "UNKNOWN"
    peers: list[str] = field(default_factory=list)


@dataclass
class HeartbeatMessage:
    """Heartbeat message for federation peers.

    DEPRECATION NOTICE:
    This legacy message format is maintained for backward compatibility with existing
    federation peers. The EFP recommendation is to use ReadinessMessage instead.

    This message contains full Slurm metrics including node, partition, and job statistics.
    """

    schema_version: str = "0.1"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    cluster: ClusterInfo = field(default_factory=lambda: ClusterInfo())  # type: ignore
    node_stats: NodeStats = field(default_factory=lambda: NodeStats())  # type: ignore
    partition_stats: list[PartitionStats] = field(default_factory=list)
    job_stats: JobStats = field(default_factory=lambda: JobStats())  # type: ignore
    resource_usage: ResourceUsage = field(default_factory=lambda: ResourceUsage())  # type: ignore
    federation: FederationInfo = field(default_factory=FederationInfo)
    signature: str | None = None
    status: str = "healthy"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "schema_version": self.schema_version,
            "timestamp": self.timestamp,
            "cluster": {
                "id": self.cluster.id,
                "name": self.cluster.name,
                "site": self.cluster.site,
                "version": self.cluster.version,
                "uptime": self.cluster.uptime,
            },
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
                "state": self.federation.state,
                "peers": self.federation.peers,
            },
            "signature": self.signature,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_metrics(
        cls, metrics: Any, cluster_info: ClusterInfo | None = None
    ) -> HeartbeatMessage:
        """Create heartbeat message from collector metrics.

        Args:
            metrics: ClusterMetrics from SlurmCollector.
            cluster_info: Optional ClusterInfo to override defaults.

        Returns:
            HeartbeatMessage with current metrics.
        """
        return cls(
            schema_version="0.1",
            timestamp=datetime.utcnow().isoformat() + "Z",
            cluster=cluster_info
            if cluster_info
            else ClusterInfo(id="unknown", name="unknown", site="unknown"),
            node_stats=metrics.node_stats,
            partition_stats=metrics.partition_stats,
            job_stats=metrics.job_stats,
            resource_usage=metrics.resource_usage,
            federation=FederationInfo(),
            signature=None,
            status="healthy",
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HeartbeatMessage:
        """Create from dictionary."""
        return cls(
            schema_version=data.get("schema_version", "0.1"),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
            cluster=ClusterInfo(
                id=data.get("cluster", {}).get("id", "unknown"),
                name=data.get("cluster", {}).get("name", "unknown"),
                site=data.get("cluster", {}).get("site", "unknown"),
                version=data.get("cluster", {}).get("version", "unknown"),
                uptime=data.get("cluster", {}).get("uptime", 0),
            ),
            node_stats=NodeStats(
                total=data.get("node_stats", {}).get("total", 0),
                idle=data.get("node_stats", {}).get("idle", 0),
                allocated=data.get("node_stats", {}).get("allocated", 0),
                drained=data.get("node_stats", {}).get("drained", 0),
                down=data.get("node_stats", {}).get("down", 0),
            ),
            partition_stats=[
                PartitionStats(
                    name=p.get("name", ""),
                    total_cpus=p.get("total_cpus", 0),
                    available_cpus=p.get("available_cpus", 0),
                    total_nodes=p.get("total_nodes", 0),
                    idle_nodes=p.get("idle_nodes", 0),
                    pending_jobs=p.get("pending_jobs", 0),
                    running_jobs=p.get("running_jobs", 0),
                )
                for p in data.get("partition_stats", [])
            ],
            job_stats=JobStats(
                pending=data.get("job_stats", {}).get("pending", 0),
                running=data.get("job_stats", {}).get("running", 0),
                completed=data.get("job_stats", {}).get("completed", 0),
                failed=data.get("job_stats", {}).get("failed", 0),
                cancelled=data.get("job_stats", {}).get("cancelled", 0),
            ),
            resource_usage=ResourceUsage(
                cpu_percent=data.get("resource_usage", {}).get("cpu_percent", 0.0),
                memory_percent=data.get("resource_usage", {}).get("memory_percent", 0.0),
                gpu_percent=data.get("resource_usage", {}).get("gpu_percent", 0.0),
            ),
            federation=FederationInfo(
                state=data.get("federation", {}).get("state", "UNKNOWN"),
                peers=data.get("federation", {}).get("peers", []),
            ),
            signature=data.get("signature"),
            status=data.get("status", "healthy"),
        )

    def sign(self, private_key: Any) -> None:
        """Sign the heartbeat message with a private key.

        Args:
            private_key: Private key object or PEM bytes.
        """
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        message_json = self.to_json()

        # Handle both key objects and PEM bytes
        if isinstance(private_key, bytes):
            private_key_obj = serialization.load_pem_private_key(
                private_key,
                password=None,
            )
        else:
            private_key_obj = private_key

        # RSA-only at runtime - suppress mypy errors for non-RSA key types
        signature = private_key_obj.sign(message_json.encode(), padding.PKCS1v15(), hashes.SHA256())  # type: ignore[union-attr, call-arg, arg-type]
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
                # RSA-only at runtime - suppress mypy errors for non-RSA key types
                from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

                if isinstance(public_key, RSAPublicKey):
                    public_key.verify(signature_bytes, message_json.encode(), padding.PKCS1v15(), hashes.SHA256())
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


__all__ = [
    "ClusterInfo",
    "FederationInfo",
    "HeartbeatMessage",
    "JobStats",
    "NodeStats",
    "PartitionStats",
    "ResourceUsage",
]
