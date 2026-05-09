"""EFP-aligned readiness schema for federation heartbeat.

This module defines the readiness message schema recommended by the EFP:
https://www.eurohpc-ju.europa.eu/supercomputers/eurohpc-federation-platform_en

The readiness signal answers: "Can this site safely receive federated work right now, and why or why not?"
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any


class ReadinessStatus(str, Enum):
    """Readiness status values aligned with EFP recommendation."""

    READY = "ready"
    LIMITED = "limited"
    DRAINING = "draining"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class QueuePressure(str, Enum):
    """Queue pressure levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Signals:
    """Readiness signals indicating why a site is/ isn't ready.

    Per EFP recommendation: These are coarse-grained signals only.
    No user, job, account, or filesystem details.
    """

    slurmctld_reachable: bool = True
    slurm_federation_visible: bool = False
    maintenance: bool = False
    accepting_new_jobs: bool = True
    queue_pressure: QueuePressure = QueuePressure.LOW
    critical_partitions_available: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "slurmctld_reachable": self.slurmctld_reachable,
            "slurm_federation_visible": self.slurm_federation_visible,
            "maintenance": self.maintenance,
            "accepting_new_jobs": self.accepting_new_jobs,
            "queue_pressure": self.queue_pressure.value
            if isinstance(self.queue_pressure, QueuePressure)
            else self.queue_pressure,
            "critical_partitions_available": self.critical_partitions_available,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Signals:
        """Create from dictionary."""
        queue_pressure_value = data.get("queue_pressure", "low")
        if isinstance(queue_pressure_value, str):
            try:
                queue_pressure = QueuePressure(queue_pressure_value)
            except ValueError:
                queue_pressure = QueuePressure.LOW
        else:
            queue_pressure = queue_pressure_value

        return cls(
            slurmctld_reachable=data.get("slurmctld_reachable", True),
            slurm_federation_visible=data.get("slurm_federation_visible", False),
            maintenance=data.get("maintenance", False),
            accepting_new_jobs=data.get("accepting_new_jobs", True),
            queue_pressure=queue_pressure,
            critical_partitions_available=data.get("critical_partitions_available", True),
        )


@dataclass
class CapacityHint:
    """Coarse-grained capacity hint.

    Per EFP recommendation: No per-user, per-project, or per-job details.
    Only aggregate capacity information.
    """

    idle_nodes: int = 0
    down_nodes: int = 0
    drained_nodes: int = 0
    pending_jobs: int = 0
    running_jobs: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "idle_nodes": self.idle_nodes,
            "down_nodes": self.down_nodes,
            "drained_nodes": self.drained_nodes,
            "pending_jobs": self.pending_jobs,
            "running_jobs": self.running_jobs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapacityHint:
        """Create from dictionary."""
        return cls(
            idle_nodes=data.get("idle_nodes", 0),
            down_nodes=data.get("down_nodes", 0),
            drained_nodes=data.get("drained_nodes", 0),
            pending_jobs=data.get("pending_jobs", 0),
            running_jobs=data.get("running_jobs", 0),
        )


@dataclass
class ReadinessMessage:
    """EFP-aligned readiness message.

    This message answers: "Can this site safely receive federated work right now, and why or why not?"

    Per EFP recommendation:
    - No user/job/account details
    - Coarse-grained capacity hints only
    - Cryptographic signature for authenticity
    - TTL-based freshness
    """

    # Fields without defaults must come before fields with defaults
    site_id: str
    cluster_name: str = ""
    observed_at: str = ""
    schema_version: str = "0.1"
    status: ReadinessStatus = ReadinessStatus.UNKNOWN
    fed_state: str = "UNKNOWN"
    reason: str = ""
    ttl_seconds: int = 90
    signals: Signals = field(default_factory=Signals)
    capacity_hint: CapacityHint = field(default_factory=CapacityHint)
    signature: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "schema_version": self.schema_version,
            "site_id": self.site_id,
            "cluster_name": self.cluster_name,
            "observed_at": self.observed_at,
            "status": self.status.value
            if isinstance(self.status, ReadinessStatus)
            else self.status,
            "fed_state": self.fed_state,
            "reason": self.reason,
            "ttl_seconds": self.ttl_seconds,
            "signals": self.signals.to_dict()
            if hasattr(self.signals, "to_dict")
            else {
                "slurmctld_reachable": self.signals.slurmctld_reachable,
                "slurm_federation_visible": getattr(
                    self.signals, "slurm_federation_visible", False
                ),
                "maintenance": self.signals.maintenance,
                "accepting_new_jobs": getattr(self.signals, "accepting_new_jobs", True),
                "queue_pressure": self.signals.queue_pressure.value
                if isinstance(self.signals.queue_pressure, QueuePressure)
                else self.signals.queue_pressure,
                "critical_partitions_available": getattr(
                    self.signals, "critical_partitions_available", True
                ),
            },
            "capacity_hint": self.capacity_hint.to_dict()
            if hasattr(self.capacity_hint, "to_dict")
            else {
                "idle_nodes": getattr(self.capacity_hint, "idle_nodes", 0),
                "down_nodes": getattr(self.capacity_hint, "down_nodes", 0),
                "drained_nodes": getattr(self.capacity_hint, "drained_nodes", 0),
                "pending_jobs": getattr(self.capacity_hint, "pending_jobs", 0),
                "running_jobs": getattr(self.capacity_hint, "running_jobs", 0),
            },
            "signature": self.signature,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReadinessMessage:
        """Create from dictionary."""
        signals_data = data.get("signals", {})
        capacity_data = data.get("capacity_hint", {})

        # Handle signals - check if it's a dict or already a Signals object
        if isinstance(signals_data, dict):
            signals = Signals.from_dict(signals_data)
        else:
            signals = signals_data

        # Handle capacity_hint - check if it's a dict or already a CapacityHint object
        if isinstance(capacity_data, dict):
            capacity_hint = CapacityHint.from_dict(capacity_data)
        else:
            capacity_hint = capacity_data

        return cls(
            site_id=data.get("site_id", ""),
            cluster_name=data.get("cluster_name", ""),
            observed_at=data.get("observed_at", datetime.utcnow().isoformat() + "Z"),
            schema_version=data.get("schema_version", "0.1"),
            status=ReadinessStatus(data.get("status", "unknown")),
            fed_state=data.get("fed_state", "UNKNOWN"),
            reason=data.get("reason", ""),
            ttl_seconds=data.get("ttl_seconds", 90),
            signals=signals,
            capacity_hint=capacity_hint,
            signature=data.get("signature"),
        )

    def is_expired(self, now: datetime | None = None) -> bool:
        """Check if the readiness message has expired based on TTL.

        Args:
            now: Optional datetime to check against. Defaults to current time.
        """
        if not self.observed_at:
            return True

        try:
            observed = datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return True

        if now is None:
            now = datetime.utcnow()
            # Make observed timezone-naive if it was parsed as naive
            if observed.tzinfo is not None:
                observed = observed.replace(tzinfo=None)
        else:
            # Ensure both datetimes have the same timezone awareness
            if now.tzinfo is None and observed.tzinfo is not None:
                observed = observed.replace(tzinfo=None)
            elif now.tzinfo is not None and observed.tzinfo is None:
                # Can't compare, assume expired
                return True

        expiry = observed + timedelta(seconds=self.ttl_seconds)

        return now > expiry

    def sign(self, private_key: Any) -> None:
        """Sign the readiness message with a private key.

        Args:
            private_key: Private key object or PEM bytes.
        """
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        message_json = self.to_json()

        # If a PEM bytes string is passed, load it
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
        """Verify the readiness message signature.

        Args:
            public_key_pem: Public key in PEM format (bytes).

        Returns:
            True if signature is valid, False otherwise.
        """
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

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
                public_key.verify(
                    signature_bytes, message_json.encode(), padding.PKCS1v15(), hashes.SHA256()
                )  # type: ignore
                return True
            finally:
                self.signature = original_signature
        except Exception:
            return False

    def get_status_reason(self) -> str:
        """Get human-readable reason for current status."""
        if self.reason:
            return self.reason

        if self.status == ReadinessStatus.READY:
            return "Site is ready to accept federated work"
        elif self.status == ReadinessStatus.LIMITED:
            return "Site has limited capacity"
        elif self.status == ReadinessStatus.DRAINING:
            return "Site is draining and not accepting new work"
        elif self.status == ReadinessStatus.UNAVAILABLE:
            return "Site is unavailable"
        else:
            return "Unknown readiness status"


__all__ = [
    "CapacityHint",
    "QueuePressure",
    "ReadinessMessage",
    "ReadinessStatus",
    "Signals",
]
