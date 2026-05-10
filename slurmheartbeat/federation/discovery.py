"""Federated capacity discovery component.

This module provides peer discovery and capacity fetching for the EuroHPC Federation Platform.

Features:
- Peer discovery from configuration or service discovery
- Health checking of federation peers
- Capacity hint fetching with timeout handling
- Support for both pull-based (ReadinessMessage) and push-based (legacy HeartbeatMessage)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from slurmheartbeat.protocol.schema import CapacityHint, ReadinessMessage, ReadinessStatus

logger = logging.getLogger(__name__)


@dataclass
class FederationPeer:
    """Representation of a federation peer."""

    name: str
    endpoint: str  # Full URL to readiness endpoint
    site: str
    capacity_hint: CapacityHint = field(default_factory=CapacityHint)
    last_seen: datetime | None = None
    status: ReadinessStatus = ReadinessStatus.UNKNOWN
    last_latency_ms: float = 0.0
    consecutive_failures: int = 0
    error: str | None = None

    def is_healthy(self, max_age_seconds: int = 120) -> bool:
        """Check if peer is healthy (recently seen and not failing)."""
        if self.last_seen is None:
            return False
        if self.consecutive_failures >= 3:
            return False
        age = (datetime.utcnow() - self.last_seen).total_seconds()
        return age <= max_age_seconds


@dataclass
class FederationState:
    """State of the federation."""

    peers: dict[str, FederationPeer] = field(default_factory=dict)
    last_update: datetime | None = None

    def get_healthy_peers(self, max_age_seconds: int = 120) -> list[FederationPeer]:
        """Get list of healthy peers."""
        return [p for p in self.peers.values() if p.is_healthy(max_age_seconds)]

    def get_total_capacity(self) -> CapacityHint:
        """Aggregate capacity across all healthy peers."""
        healthy = self.get_healthy_peers()
        total_idle = sum(p.capacity_hint.idle_nodes for p in healthy)
        total_down = sum(p.capacity_hint.down_nodes for p in healthy)
        total_drained = sum(p.capacity_hint.drained_nodes for p in healthy)
        total_pending = sum(p.capacity_hint.pending_jobs for p in healthy)
        total_running = sum(p.capacity_hint.running_jobs for p in healthy)

        return CapacityHint(
            idle_nodes=total_idle,
            down_nodes=total_down,
            drained_nodes=total_drained,
            pending_jobs=total_pending,
            running_jobs=total_running,
        )


class FederationDiscovery:
    """Discovers and manages federation peers."""

    def __init__(self, config: Any, http_client: httpx.AsyncClient | None = None):
        """Initialize federation discovery.

        Args:
            config: Client configuration with federation.peers list.
            http_client: Optional HTTP client for peer communication.
        """
        self.config = config
        self.state = FederationState()
        self._http_client = http_client
        self._lock = asyncio.Lock()

    async def discover_peers(self) -> list[FederationPeer]:
        """Discover peers from configuration.

        Returns:
            List of discovered peers.
        """
        if not hasattr(self.config, "client") or not hasattr(self.config.client, "federation"):
            logger.warning("No federation configuration found")
            return []

        federation_config = self.config.client.federation
        peer_configs = getattr(federation_config, "peers", [])

        peers = []
        for peer_config in peer_configs:
            peer = FederationPeer(
                name=peer_config.name,
                endpoint=peer_config.endpoint.rstrip("/") + "/readiness",
                site=peer_config.site,
            )
            peers.append(peer)
            self.state.peers[peer.name] = peer

        logger.info(f"Discovered {len(peers)} federation peers")
        return peers

    async def fetch_peer_capacity(self, peer: FederationPeer, timeout: int = 30) -> CapacityHint | None:
        """Fetch capacity hint from a peer.

        Args:
            peer: Peer to fetch from.
            timeout: Request timeout in seconds.

        Returns:
            CapacityHint if successful, None otherwise.
        """
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=timeout)

        try:
            start_time = datetime.utcnow()
            response = await self._http_client.get(peer.endpoint, timeout=timeout)
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            if response.status_code != 200:
                peer.error = f"HTTP {response.status_code}"
                peer.consecutive_failures += 1
                return None

            data = response.json()
            readiness = ReadinessMessage.from_dict(data)

            # Update peer state
            peer.capacity_hint = readiness.capacity_hint
            peer.last_seen = datetime.utcnow()
            peer.status = readiness.status
            peer.last_latency_ms = latency_ms
            peer.consecutive_failures = 0
            peer.error = None

            return readiness.capacity_hint

        except httpx.TimeoutException:
            peer.error = "Request timeout"
            peer.consecutive_failures += 1
            logger.warning(f"Timeout fetching from {peer.name}: {peer.error}")
            return None
        except httpx.HTTPError as e:
            peer.error = str(e)
            peer.consecutive_failures += 1
            logger.warning(f"HTTP error fetching from {peer.name}: {peer.error}")
            return None
        except Exception as e:
            peer.error = str(e)
            peer.consecutive_failures += 1
            logger.error(f"Error fetching from {peer.name}: {e}")
            return None

    async def fetch_all_peers(self, timeout: int = 30) -> dict[str, CapacityHint | None]:
        """Fetch capacity from all healthy peers in parallel.

        Args:
            timeout: Request timeout in seconds.

        Returns:
            Dictionary mapping peer name to CapacityHint or None on failure.
        """
        if not self.state.peers:
            await self.discover_peers()

        tasks = []
        for peer in self.state.peers.values():
            # Skip peers with too many consecutive failures
            if peer.consecutive_failures >= 3:
                logger.debug(f"Skipping unhealthy peer {peer.name}")
                continue
            tasks.append(self.fetch_peer_capacity(peer, timeout))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Type ignore needed because asyncio.gather with return_exceptions=True
        # returns a union that mypy cannot narrow in comprehensions
        return {
            peer.name: (result if not isinstance(result, Exception) else None)  # type: ignore
            for peer, result in zip(self.state.peers.values(), results, strict=True)
        }

    async def update_all_peers(self, timeout: int = 30) -> FederationState:
        """Update state of all peers.

        Args:
            timeout: Request timeout in seconds.

        Returns:
            Updated FederationState.
        """
        async with self._lock:
            await self.fetch_all_peers(timeout)
            self.state.last_update = datetime.utcnow()
            return self.state

    def get_federation_summary(self) -> dict[str, Any]:
        """Get summary of federation state.

        Returns:
            Dictionary with federation summary.
        """
        healthy_peers = self.state.get_healthy_peers()
        total_capacity = self.state.get_total_capacity()

        return {
            "peer_count": len(self.state.peers),
            "healthy_peer_count": len(healthy_peers),
            "total_idle_nodes": total_capacity.idle_nodes,
            "total_down_nodes": total_capacity.down_nodes,
            "total_drained_nodes": total_capacity.drained_nodes,
            "total_pending_jobs": total_capacity.pending_jobs,
            "total_running_jobs": total_capacity.running_jobs,
            "last_update": self.state.last_update.isoformat() if self.state.last_update else None,
        }

    async def close(self) -> None:
        """Close HTTP client if created."""
        if self._http_client is not None:
            await self._http_client.aclose()
