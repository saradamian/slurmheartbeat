"""EFP-aligned readiness schema for federation heartbeat.

This module defines the readiness message schema recommended by the EFP:
https://www.eurohpc-ju.europa.eu/supercomputers/eurohpc-federation-platform_en

The readiness signal answers: "Can this site safely receive federated work right now, and why or why not?"
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ReadinessStatus(str, Enum):
    """Recommended readiness statuses per EFP recommendation."""

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
    """Readiness signals indicating site state.

    Per EFP recommendation:
    - slurmctld_reachable: Is the Slurm controller reachable?
    - slurm_federation_visible: Is federation visible in Slurm?
    - maintenance: Is the site in maintenance mode?
    - accepting_new_jobs: Is the site accepting new federated jobs?
    - queue_pressure: Current queue pressure level
    - critical_partitions_available: Are critical partitions available?
    """

    slurmctld_reachable: bool = True
    slurm_federation_visible: bool = True
    maintenance: bool = False
    accepting_new_jobs: bool = True
    queue_pressure: QueuePressure = QueuePressure.NORMAL
    critical_partitions_available: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "slurmctld_reachable": self.slurmctld_reachable,
            "slurm_federation_visible": self.slurm_federation_visible,
            "maintenance": self.maintenance,
            "accepting_new_jobs": self.accepting_new_jobs,
            "queue_pressure": self.queue_pressure.value,
            "critical_partitions_available": self.critical_partitions_available,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Signals:
        """Create from dictionary."""
        return cls(
            slurmctld_reachable=data.get("slurmctld_reachable", True),
            slurm_federation_visible=data.get("slurm_federation_visible", True),
            maintenance=data.get("maintenance", False),
            accepting_new_jobs=data.get("accepting_new_jobs", True),
            queue_pressure=QueuePressure(data.get("queue_pressure", "normal")),
            critical_partitions_available=data.get("critical_partitions_available", True),
        )


@dataclass
class CapacityHint:
    """Capacity hints for scheduling decisions.

    Per EFP recommendation - coarse-grained capacity indicators:
    - idle_nodes: Number of idle nodes
    - down_nodes: Number of down nodes
    - drained_nodes: Number of drained nodes
    - pending_jobs: Number of pending jobs
    - running_jobs: Number of running jobs

    Note: These are aggregate counts only. No user/job/account details.
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

    Schema version 0.1 aligned with EFP recommendation:
    https://www.eurohpc-ju.europa.eu/supercomputers/eurohpc-federation-platform_en

    This message answers: "Can this site safely receive federated work right now?"

    Fields:
        schema_version: Schema version for compatibility checking
        site_id: Unique site identifier (e.g., "lumi", "leonardo")
        cluster_name: Local cluster name (e.g., "lumi-prod")
        observed_at: Timestamp when this readiness was observed (ISO 8601)
        status: Readiness status (ready, limited, draining, unavailable, unknown)
        fed_state: Federation state from Slurm (e.g., "ACTIVE", "INACTIVE")
        reason: Human-readable explanation for status
        ttl_seconds: Time-to-live for this readiness (consumers should treat expired as unknown)
        signals: Detailed readiness signals
        capacity_hint: Coarse capacity indicators
        signature: Optional cryptographic signature for verification
    """

    schema_version: str = "0.1"
    site_id: str = "unknown"
    cluster_name: str = "unknown"
    observed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    status: ReadinessStatus = ReadinessStatus.UNKNOWN
    fed_state: str = "UNKNOWN"
    reason: str = ""
    ttl_seconds: int = 90
    signals: Signals = field(default_factory=Signals)
    capacity_hint: CapacityHint = field(default_factory=CapacityHint)
    signature: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "schema_version": self.schema_version,
            "site_id": self.site_id,
            "cluster_name": self.cluster_name,
            "observed_at": self.observed_at,
            "status": self.status.value,
            "fed_state": self.fed_state,
            "reason": self.reason,
            "ttl_seconds": self.ttl_seconds,
            "signals": self.signals.to_dict(),
            "capacity_hint": self.capacity_hint.to_dict(),
            "signature": self.signature,
        }

    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReadinessMessage:
        """Create message from dictionary."""
        signals_data = data.get("signals", {})
        signals = Signals.from_dict(signals_data) if signals_data else Signals()

        capacity_data = data.get("capacity_hint", {})
        capacity = CapacityHint.from_dict(capacity_data) if capacity_data else CapacityHint()

        return cls(
            schema_version=data.get("schema_version", "0.1"),
            site_id=data.get("site_id", "unknown"),
            cluster_name=data.get("cluster_name", "unknown"),
            observed_at=data.get("observed_at", datetime.utcnow().isoformat() + "Z"),
            status=ReadinessStatus(data.get("status", "unknown")),
            fed_state=data.get("fed_state", "UNKNOWN"),
            reason=data.get("reason", ""),
            ttl_seconds=data.get("ttl_seconds", 90),
            signals=signals,
            capacity_hint=capacity,
            signature=data.get("signature"),
        )

    def is_expired(self, now: datetime | None = None) -> bool:
        """Check if this readiness message is expired.

        Per EFP recommendation: consumers must treat expired data as unknown.

        Args:
            now: Current time (defaults to utcnow)

        Returns:
            True if the message is expired (observed_at + ttl_seconds < now)
        """
        if now is None:
            now = datetime.utcnow()

        # Parse observed_at timestamp
        try:
            observed_str = self.observed_at.replace("Z", "+00:00")
            observed = datetime.fromisoformat(observed_str)
            # Make now timezone-aware if observed is
            if observed.tzinfo is not None:
                from datetime import timezone

                now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now
        except (ValueError, AttributeError):
            return True  # Invalid timestamp = expired

        # Calculate expiry
        from datetime import timedelta

        expiry = observed + timedelta(seconds=self.ttl_seconds)

        return now > expiry

    def sign(self, private_key) -> None:
        """Sign the readiness message with a private key.

        Args:
            private_key: Private key object (cryptography.hazmat.primitives.asymmetric.rsa.RSAPrivateKey).
        """
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        message_json = self.to_json()

        # If a PEM bytes string is passed, load it
        if isinstance(private_key, bytes):
            private_key = serialization.load_pem_private_key(
                private_key,
                password=None,
            )

        signature = private_key.sign(message_json.encode(), padding.PKCS1v15(), hashes.SHA256())
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
                public_key.verify(
                    signature_bytes, message_json.encode(), padding.PKCS1v15(), hashes.SHA256()
                )
                return True
            finally:
                self.signature = original_signature
        except Exception:
            return False

    def get_status_reason(self) -> str:
        """Get human-readable reason for current status."""
        if self.status == ReadinessStatus.READY:
            return "Site is ready to accept federated work"
        elif self.status == ReadinessStatus.LIMITED:
            return "Site has limited capacity or is in maintenance"
        elif self.status == ReadinessStatus.DRAINING:
            return "Site is draining and not accepting new work"
        elif self.status == ReadinessStatus.UNAVAILABLE:
            return "Site is unavailable or unhealthy"
        elif self.status == ReadinessStatus.UNKNOWN:
            return "Site readiness is unknown"
        return self.reason or "No reason provided"


__all__ = [
    "CapacityHint",
    "QueuePressure",
    "ReadinessMessage",
    "ReadinessStatus",
    "Signals",
]
