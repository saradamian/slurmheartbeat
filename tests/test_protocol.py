"""Tests for Slurm Heartbeat protocol."""

from __future__ import annotations

from slurmheartbeat.protocol.message import (
    ClusterInfo,
    FederationInfo,
    HeartbeatMessage,
    JobStats,
    NodeStats,
    PartitionStats,
    ResourceUsage,
)


class TestHeartbeatMessage:
    """Tests for HeartbeatMessage class."""

    def test_create_message(self):
        """Test creating a heartbeat message."""
        message = HeartbeatMessage(
            cluster=ClusterInfo(id="test", name="test-cluster", site="test-site"),
        )

        assert message.schema_version == "0.1"
        assert message.cluster.id == "test"
        assert message.get_status() == "healthy"

    def test_message_to_dict(self):
        """Test message serialization to dictionary."""
        message = HeartbeatMessage(
            cluster=ClusterInfo(id="test", name="test-cluster", site="test-site", uptime=1000),
            node_stats=NodeStats(total=10, idle=5, allocated=4, drained=1, down=0),
        )

        data = message.to_dict()

        assert data["schema_version"] == "0.1"
        assert data["cluster"]["id"] == "test"
        assert data["node_stats"]["total"] == 10
        # Note: to_dict() doesn't include "status" - it's computed by get_status()
        assert "status" not in data  # status is not stored, it's computed

    def test_message_from_dict(self):
        """Test message deserialization from dictionary."""
        data = {
            "schema_version": "0.1",
            "timestamp": "2025-01-09T12:00:00Z",
            "cluster": {
                "id": "test",
                "name": "test-cluster",
                "site": "test-site",
                "version": "24.05.0",
                "uptime": 1000,
            },
            "node_stats": {
                "total": 10,
                "idle": 5,
                "allocated": 4,
                "drained": 1,
                "down": 0,
            },
            "partition_stats": [],
            "job_stats": {
                "pending": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
            },
            "resource_usage": {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "gpu_percent": 0.0,
            },
            "federation": {
                "state": "UNKNOWN",
                "peers": [],
            },
            "signature": None,
        }

        message = HeartbeatMessage.from_dict(data)

        assert message.cluster.id == "test"
        assert message.cluster.name == "test-cluster"
        assert message.get_status() == "degraded"  # 1 drained out of 10 total = degraded
        assert message.node_stats.total == 10

    def test_message_roundtrip(self):
        """Test message serialization and deserialization roundtrip."""
        original = HeartbeatMessage(
            cluster=ClusterInfo(id="test", name="test-cluster", site="test-site"),
            node_stats=NodeStats(total=10, idle=5, allocated=4, drained=1, down=0),
            job_stats=JobStats(pending=5, running=10, completed=100, failed=2, cancelled=3),
        )

        # Serialize and deserialize
        data = original.to_dict()
        restored = HeartbeatMessage.from_dict(data)

        # Verify all fields
        assert restored.cluster.id == original.cluster.id
        assert restored.cluster.name == original.cluster.name
        assert restored.get_status() == original.get_status()
        assert restored.node_stats.total == original.node_stats.total
        assert restored.job_stats.running == original.job_stats.running

    def test_message_to_json(self):
        """Test message JSON serialization."""
        message = HeartbeatMessage(
            cluster=ClusterInfo(id="test", name="test-cluster", site="test-site"),
        )

        json_str = message.to_json()

        assert isinstance(json_str, str)
        assert "test" in json_str
        # Note: "healthy" is not in the JSON because status is computed, not stored
        assert "schema_version" in json_str

    def test_get_status_healthy(self):
        """Test status calculation for healthy cluster."""
        message = HeartbeatMessage(
            cluster=ClusterInfo(id="test", name="test", site="test"),
            node_stats=NodeStats(total=10, idle=8, allocated=2, drained=0, down=0),
        )

        assert message.get_status() == "healthy"

    def test_get_status_degraded(self):
        """Test status calculation for degraded cluster."""
        message = HeartbeatMessage(
            cluster=ClusterInfo(id="test", name="test", site="test"),
            node_stats=NodeStats(total=10, idle=5, allocated=3, drained=2, down=0),
        )

        assert message.get_status() == "degraded"

    def test_get_status_unhealthy_down(self):
        """Test status calculation for unhealthy cluster (down nodes)."""
        message = HeartbeatMessage(
            cluster=ClusterInfo(id="test", name="test", site="test"),
            node_stats=NodeStats(total=10, idle=5, allocated=3, drained=0, down=2),
        )

        assert message.get_status() == "unhealthy"

    def test_get_status_unhealthy_drained(self):
        """Test status calculation for unhealthy cluster (high drained)."""
        message = HeartbeatMessage(
            cluster=ClusterInfo(id="test", name="test", site="test"),
            node_stats=NodeStats(total=10, idle=2, allocated=2, drained=6, down=0),
        )

        assert message.get_status() == "unhealthy"


class TestClusterInfo:
    """Tests for ClusterInfo class."""

    def test_create_cluster_info(self):
        """Test creating cluster info."""
        info = ClusterInfo(id="test", name="test-cluster", site="test-site")

        assert info.id == "test"
        assert info.name == "test-cluster"
        assert info.site == "test-site"


class TestNodeStats:
    """Tests for NodeStats class."""

    def test_create_node_stats(self):
        """Test creating node stats."""
        stats = NodeStats(total=10, idle=5, allocated=4, drained=1, down=0)

        assert stats.total == 10
        assert stats.idle == 5
        assert stats.allocated == 4
        assert stats.drained == 1
        assert stats.down == 0


class TestPartitionStats:
    """Tests for PartitionStats class."""

    def test_create_partition_stats(self):
        """Test creating partition stats."""
        stats = PartitionStats(
            name="standard",
            total_cpus=1000,
            available_cpus=800,
            total_nodes=10,
            idle_nodes=5,
            pending_jobs=2,
            running_jobs=3,
        )

        assert stats.name == "standard"
        assert stats.total_cpus == 1000
        assert stats.running_jobs == 3


class TestJobStats:
    """Tests for JobStats class."""

    def test_create_job_stats(self):
        """Test creating job stats."""
        stats = JobStats(pending=5, running=10, completed=100, failed=2, cancelled=3)

        assert stats.pending == 5
        assert stats.running == 10
        assert stats.failed == 2


class TestResourceUsage:
    """Tests for ResourceUsage class."""

    def test_create_resource_usage(self):
        """Test creating resource usage."""
        usage = ResourceUsage(cpu_percent=75.5, memory_percent=60.2, gpu_percent=90.0)

        assert usage.cpu_percent == 75.5
        assert usage.memory_percent == 60.2
        assert usage.gpu_percent == 90.0


class TestFederationInfo:
    """Tests for FederationInfo class."""

    def test_create_federation_info(self):
        """Test creating federation info."""
        info = FederationInfo(
            state="ACTIVE",
            peers=["peer1", "peer2"],
        )

        assert info.state == "ACTIVE"
        assert info.peers == ["peer1", "peer2"]
