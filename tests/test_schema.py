"""Tests for EFP readiness schema.

Per EFP recommendation:
- Test ReadinessMessage schema alignment
- Test status determination logic
- Test signal and capacity hint serialization
- Test signature verification
"""

from __future__ import annotations

from datetime import datetime

from slurmheartbeat.protocol.schema import (
    CapacityHint,
    QueuePressure,
    ReadinessMessage,
    ReadinessStatus,
    Signals,
)


class TestReadinessMessage:
    """Tests for ReadinessMessage class."""

    def test_create_readiness_message(self):
        """Test creating a readiness message."""
        message = ReadinessMessage(
            site_id="lumi",
            cluster_name="lumi-prod",
            status=ReadinessStatus.READY,
        )

        assert message.schema_version == "0.1"
        assert message.site_id == "lumi"
        assert message.cluster_name == "lumi-prod"
        assert message.status == ReadinessStatus.READY
        assert message.ttl_seconds == 90

    def test_message_to_dict(self):
        """Test message serialization to dictionary."""
        message = ReadinessMessage(
            site_id="lumi",
            cluster_name="lumi-prod",
            status=ReadinessStatus.READY,
            fed_state="ACTIVE",
            reason="scheduler_accepting_work",
            signals=Signals(slurmctld_reachable=True, queue_pressure=QueuePressure.NORMAL),
            capacity_hint=CapacityHint(idle_nodes=42, running_jobs=820),
        )

        data = message.to_dict()

        assert data["schema_version"] == "0.1"
        assert data["site_id"] == "lumi"
        assert data["status"] == "ready"
        assert data["fed_state"] == "ACTIVE"
        assert data["signals"]["queue_pressure"] == "normal"
        assert data["capacity_hint"]["idle_nodes"] == 42

    def test_message_from_dict(self):
        """Test message deserialization from dictionary."""
        data = {
            "schema_version": "0.1",
            "site_id": "lumi",
            "cluster_name": "lumi-prod",
            "observed_at": "2026-05-01T21:30:00Z",
            "status": "ready",
            "fed_state": "ACTIVE",
            "reason": "scheduler_accepting_work",
            "ttl_seconds": 90,
            "signals": {
                "slurmctld_reachable": True,
                "slurm_federation_visible": True,
                "maintenance": False,
                "accepting_new_jobs": True,
                "queue_pressure": "normal",
                "critical_partitions_available": True,
            },
            "capacity_hint": {
                "idle_nodes": 42,
                "down_nodes": 0,
                "drained_nodes": 3,
                "pending_jobs": 120,
                "running_jobs": 820,
            },
            "signature": None,
        }

        message = ReadinessMessage.from_dict(data)

        assert message.schema_version == "0.1"
        assert message.site_id == "lumi"
        assert message.status == ReadinessStatus.READY
        assert message.fed_state == "ACTIVE"
        assert message.signals.queue_pressure == QueuePressure.NORMAL
        assert message.capacity_hint.idle_nodes == 42

    def test_message_roundtrip(self):
        """Test message serialization and deserialization roundtrip."""
        original = ReadinessMessage(
            site_id="lumi",
            cluster_name="lumi-prod",
            status=ReadinessStatus.LIMITED,
            fed_state="ACTIVE",
            reason="high_queue_pressure",
            signals=Signals(
                slurmctld_reachable=True,
                queue_pressure=QueuePressure.HIGH,
                maintenance=False,
            ),
            capacity_hint=CapacityHint(idle_nodes=10, pending_jobs=500),
        )

        # Serialize and deserialize
        data = original.to_dict()
        restored = ReadinessMessage.from_dict(data)

        # Verify all fields
        assert restored.site_id == original.site_id
        assert restored.cluster_name == original.cluster_name
        assert restored.status == original.status
        assert restored.fed_state == original.fed_state
        assert restored.signals.queue_pressure == original.signals.queue_pressure
        assert restored.capacity_hint.idle_nodes == original.capacity_hint.idle_nodes

    def test_message_to_json(self):
        """Test message JSON serialization."""
        message = ReadinessMessage(
            site_id="lumi",
            cluster_name="lumi-prod",
            status=ReadinessStatus.READY,
        )

        json_str = message.to_json()

        assert isinstance(json_str, str)
        assert "lumi" in json_str
        assert "ready" in json_str
        assert "schema_version" in json_str

    def test_is_expired_not_expired(self):
        """Test is_expired for non-expired message."""
        message = ReadinessMessage(
            site_id="lumi",
            status=ReadinessStatus.READY,
            observed_at="2026-05-01T21:30:00Z",
            ttl_seconds=90,
        )

        # Check at 30 seconds after observed
        now = datetime(2026, 5, 1, 21, 30, 30)
        assert not message.is_expired(now)

    def test_is_expired_expired(self):
        """Test is_expired for expired message."""
        message = ReadinessMessage(
            site_id="lumi",
            status=ReadinessStatus.READY,
            observed_at="2026-05-01T21:30:00Z",
            ttl_seconds=90,
        )

        # Check at 120 seconds after observed (beyond TTL)
        now = datetime(2026, 5, 1, 21, 32, 0)
        assert message.is_expired(now)

    def test_is_expired_invalid_timestamp(self):
        """Test is_expired for invalid timestamp."""
        message = ReadinessMessage(
            site_id="lumi",
            status=ReadinessStatus.READY,
            observed_at="invalid-timestamp",
            ttl_seconds=90,
        )

        assert message.is_expired()  # Invalid timestamp = expired

    def test_get_status_reason_ready(self):
        """Test get_status_reason for ready status."""
        message = ReadinessMessage(
            site_id="lumi",
            status=ReadinessStatus.READY,
        )

        assert "ready to accept" in message.get_status_reason().lower()

    def test_get_status_reason_limited(self):
        """Test get_status_reason for limited status."""
        message = ReadinessMessage(
            site_id="lumi",
            status=ReadinessStatus.LIMITED,
        )

        assert "limited capacity" in message.get_status_reason().lower()

    def test_get_status_reason_draining(self):
        """Test get_status_reason for draining status."""
        message = ReadinessMessage(
            site_id="lumi",
            status=ReadinessStatus.DRAINING,
        )

        assert "draining" in message.get_status_reason().lower()

    def test_get_status_reason_unavailable(self):
        """Test get_status_reason for unavailable status."""
        message = ReadinessMessage(
            site_id="lumi",
            status=ReadinessStatus.UNAVAILABLE,
        )

        assert "unavailable" in message.get_status_reason().lower()

    def test_get_status_reason_unknown(self):
        """Test get_status_reason for unknown status."""
        message = ReadinessMessage(
            site_id="lumi",
            status=ReadinessStatus.UNKNOWN,
        )

        assert "unknown" in message.get_status_reason().lower()


class TestSignals:
    """Tests for Signals class."""

    def test_create_signals(self):
        """Test creating signals."""
        signals = Signals(
            slurmctld_reachable=True,
            slurm_federation_visible=True,
            maintenance=False,
            accepting_new_jobs=True,
            queue_pressure=QueuePressure.NORMAL,
            critical_partitions_available=True,
        )

        assert signals.slurmctld_reachable is True
        assert signals.queue_pressure == QueuePressure.NORMAL

    def test_signals_to_dict(self):
        """Test signals serialization."""
        signals = Signals(
            slurmctld_reachable=True,
            queue_pressure=QueuePressure.HIGH,
            maintenance=True,
        )

        data = signals.to_dict()

        assert data["slurmctld_reachable"] is True
        assert data["queue_pressure"] == "high"
        assert data["maintenance"] is True

    def test_signals_from_dict(self):
        """Test signals deserialization."""
        data = {
            "slurmctld_reachable": True,
            "slurm_federation_visible": False,
            "maintenance": True,
            "accepting_new_jobs": False,
            "queue_pressure": "critical",
            "critical_partitions_available": False,
        }

        signals = Signals.from_dict(data)

        assert signals.slurmctld_reachable is True
        assert signals.maintenance is True
        assert signals.queue_pressure == QueuePressure.CRITICAL
        assert signals.accepting_new_jobs is False


class TestCapacityHint:
    """Tests for CapacityHint class."""

    def test_create_capacity_hint(self):
        """Test creating capacity hint."""
        hint = CapacityHint(
            idle_nodes=42,
            down_nodes=0,
            drained_nodes=3,
            pending_jobs=120,
            running_jobs=820,
        )

        assert hint.idle_nodes == 42
        assert hint.running_jobs == 820

    def test_capacity_hint_to_dict(self):
        """Test capacity hint serialization."""
        hint = CapacityHint(idle_nodes=42, pending_jobs=120)

        data = hint.to_dict()

        assert data["idle_nodes"] == 42
        assert data["pending_jobs"] == 120

    def test_capacity_hint_from_dict(self):
        """Test capacity hint deserialization."""
        data = {
            "idle_nodes": 42,
            "down_nodes": 5,
            "drained_nodes": 3,
            "pending_jobs": 120,
            "running_jobs": 820,
        }

        hint = CapacityHint.from_dict(data)

        assert hint.idle_nodes == 42
        assert hint.down_nodes == 5
        assert hint.running_jobs == 820


class TestQueuePressure:
    """Tests for QueuePressure enum."""

    def test_queue_pressure_values(self):
        """Test QueuePressure enum values."""
        assert QueuePressure.LOW.value == "low"
        assert QueuePressure.NORMAL.value == "normal"
        assert QueuePressure.HIGH.value == "high"
        assert QueuePressure.CRITICAL.value == "critical"

    def test_queue_pressure_from_string(self):
        """Test QueuePressure from string."""
        assert QueuePressure("normal") == QueuePressure.NORMAL
        assert QueuePressure("critical") == QueuePressure.CRITICAL


class TestReadinessStatus:
    """Tests for ReadinessStatus enum."""

    def test_readiness_status_values(self):
        """Test ReadinessStatus enum values."""
        assert ReadinessStatus.READY.value == "ready"
        assert ReadinessStatus.LIMITED.value == "limited"
        assert ReadinessStatus.DRAINING.value == "draining"
        assert ReadinessStatus.UNAVAILABLE.value == "unavailable"
        assert ReadinessStatus.UNKNOWN.value == "unknown"

    def test_readiness_status_from_string(self):
        """Test ReadinessStatus from string."""
        assert ReadinessStatus("ready") == ReadinessStatus.READY
        assert ReadinessStatus("limited") == ReadinessStatus.LIMITED
        assert ReadinessStatus("draining") == ReadinessStatus.DRAINING
        assert ReadinessStatus("unavailable") == ReadinessStatus.UNAVAILABLE
        assert ReadinessStatus("unknown") == ReadinessStatus.UNKNOWN
