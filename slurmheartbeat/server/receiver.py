"""Heartbeat receiver server for federation peers.

DEPRECATION NOTICE:
This legacy P2P receiver is maintained for backward compatibility with existing
federation peers. The EFP recommendation is to use pull-based readiness publishing
via the ReadinessPublisher's /readiness endpoint instead.

This receiver:
- Accepts push-based heartbeats from peers
- Maintains peer state and health
- Will be deprecated when all peers migrate to pull-based model

WARNING: This module is deprecated and may be removed in a future release.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slurmheartbeat.client.config import ServerConfig
    from slurmheartbeat.protocol.message import HeartbeatMessage

logger = logging.getLogger(__name__)


@dataclass
class PeerState:
    """State of a federation peer."""

    name: str
    endpoint: str = ""
    site: str = ""
    status: str = "unknown"
    last_seen: datetime | None = None
    last_latency_ms: float = 0.0
    consecutive_failures: int = 0
    error: str | None = None


class FederationState:
    """Federation state management for peer tracking."""

    def __init__(self, config: ServerConfig):
        """Initialize federation state.

        Args:
            config: Server configuration with peer list.
        """
        self.config = config
        self._peers: dict[str, PeerState] = {}
        self._lock = asyncio.Lock()
        self._peer_public_keys: dict[str, str] = {}
        self._allowed_members: list[str] = []

    async def update_peer(
        self, peer_name: str, message: HeartbeatMessage, latency_ms: float
    ) -> PeerState:
        """Update peer state based on received heartbeat."""
        async with self._lock:
            if peer_name not in self._peers:
                self._peers[peer_name] = PeerState(name=peer_name)

            peer = self._peers[peer_name]
            peer.last_seen = datetime.utcnow()
            peer.status = message.get_status()
            peer.last_latency_ms = latency_ms
            peer.consecutive_failures = 0
            peer.error = None

            return peer

    async def record_failure(self, peer_name: str, error: str) -> PeerState:
        """Record a failed heartbeat from a peer."""
        async with self._lock:
            if peer_name not in self._peers:
                self._peers[peer_name] = PeerState(name=peer_name)

            peer = self._peers[peer_name]
            peer.consecutive_failures += 1
            peer.error = error

            return peer

    async def get_peer(self, peer_name: str) -> PeerState | None:
        """Get peer state by name."""
        async with self._lock:
            return self._peers.get(peer_name)

    async def get_all_peers(self) -> list[PeerState]:
        """Get all peer states."""
        async with self._lock:
            return list(self._peers.values())

    async def get_healthy_peers(self) -> list[PeerState]:
        """Get all healthy peers (no consecutive failures)."""
        async with self._lock:
            return [p for p in self._peers.values() if p.consecutive_failures == 0]

    def set_peer_public_key(self, peer_name: str, public_key: str) -> None:
        """Set public key for a peer."""
        self._peer_public_keys[peer_name] = public_key

    def get_peer_public_key(self, peer_name: str) -> str | None:
        """Get public key for a peer."""
        return self._peer_public_keys.get(peer_name)

    def set_allowed_members(self, members: list[str]) -> None:
        """Set allowed federation members."""
        self._allowed_members = members

    def get_allowed_members(self) -> list[str]:
        """Get allowed federation members."""
        return self._allowed_members


class HeartbeatReceiver:
    """Receives heartbeat messages from federation peers.

    DEPRECATED: This legacy P2P receiver is maintained for backward compatibility.
    The EFP recommendation is to use pull-based readiness publishing instead.
    """

    def __init__(self, config: ServerConfig):
        """Initialize the heartbeat receiver.

        Args:
            config: Server configuration with peer list.
        """
        self.config = config
        self.state = FederationState(config)
        self._request_counts: dict[str, list[float]] = {}
        self._rate_limit_window = 60  # seconds
        self._rate_limit_max_requests = 100  # per window
        self._server = None

    async def update_peer(
        self, peer_name: str, message: HeartbeatMessage, latency_ms: float
    ) -> PeerState:
        """Update peer state based on received heartbeat."""
        return await self.state.update_peer(peer_name, message, latency_ms)

    async def record_failure(self, peer_name: str, error: str) -> PeerState:
        """Record a failed heartbeat from a peer."""
        return await self.state.record_failure(peer_name, error)

    async def get_peer(self, peer_name: str) -> PeerState | None:
        """Get peer state by name."""
        return await self.state.get_peer(peer_name)

    async def get_all_peers(self) -> list[PeerState]:
        """Get all peer states."""
        return await self.state.get_all_peers()

    async def get_healthy_peers(self) -> list[PeerState]:
        """Get all healthy peers (no consecutive failures)."""
        return await self.state.get_healthy_peers()

    def set_peer_public_key(self, peer_name: str, public_key: str) -> None:
        """Set public key for a peer."""
        self.state.set_peer_public_key(peer_name, public_key)

    def get_peer_public_key(self, peer_name: str) -> str | None:
        """Get public key for a peer."""
        return self.state.get_peer_public_key(peer_name)

    async def get_state(self) -> dict:
        """Get current federation state."""
        async with self.state._lock:
            peers = list(self.state._peers.values())

        return {
            "peers": [
                {
                    "name": p.name,
                    "endpoint": p.endpoint,
                    "site": p.site,
                    "status": p.status,
                    "last_seen": p.last_seen.isoformat() if p.last_seen else None,
                    "last_latency_ms": p.last_latency_ms,
                    "consecutive_failures": p.consecutive_failures,
                    "error": p.error,
                }
                for p in peers
            ]
        }

    async def _handle_heartbeat(self, request) -> dict:
        """Handle incoming heartbeat request."""
        # Placeholder for HTTP handler
        return {"status": "ok"}

    async def _handle_health(self, request) -> dict:
        """Handle health check request."""
        return {"status": "healthy"}

    async def _handle_peers(self, request) -> dict:
        """Handle peers list request."""
        peers = await self.state.get_all_peers()
        return {"peers": [p.name for p in peers]}

    async def start(self) -> None:
        """Start the receiver server."""
        logger.info("Starting heartbeat receiver")
        # Placeholder for server startup

    async def stop(self) -> None:
        """Stop the receiver server."""
        logger.info("Stopping heartbeat receiver")
        if self._server:
            await self._server.stop()


__all__ = ["FederationState", "HeartbeatReceiver", "PeerState"]
