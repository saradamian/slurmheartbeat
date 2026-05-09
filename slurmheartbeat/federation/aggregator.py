"""Federated capacity aggregator for EFP.

This module provides a federated capacity discovery service that aggregates
readiness signals from multiple EuroHPC sites to answer:
"Where can I run my job right now?"

Per EFP gap analysis:
- No unified capacity discovery across sites exists
- Researchers need to know WHERE to run jobs, not just HOW to access systems
- This component aggregates readiness signals and provides capacity queries
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiohttp
from slurmheartbeat.protocol.schema import ReadinessStatus

logger = logging.getLogger(__name__)


@dataclass
class FederatedSite:
    """Federated site with aggregated capacity information."""

    site_id: str
    cluster_name: str
    status: ReadinessStatus
    observed_at: datetime
    idle_nodes: int = 0
    allocated_nodes: int = 0
    pending_jobs: int = 0
    running_jobs: int = 0
    slurmctld_reachable: bool = True
    maintenance: bool = False
    ttl_seconds: int = 90


@dataclass
class CapacityQuery:
    """Query for federated capacity."""

    min_idle_nodes: int = 0
    min_gpu_nodes: int = 0
    max_pending_jobs: int | None = None
    required_status: ReadinessStatus | None = None
    exclude_sites: list[str] = field(default_factory=list)


@dataclass
class CapacityResult:
    """Result of a capacity query."""

    sites: list[FederatedSite]
    total_idle_nodes: int
    total_allocated_nodes: int
    query_time_ms: float
    timestamp: datetime


class FederatedCapacityAggregator:
    """Aggregates readiness signals from multiple EFP sites.

    Provides:
    - /federated-capacity endpoint for capacity discovery
    - Query-based filtering (min nodes, max queue pressure, etc.)
    - Real-time aggregation from peer sites
    - TTL-based freshness validation
    """

    def __init__(
        self,
        peers: list[dict[str, Any]],
        timeout_seconds: int = 10,
        refresh_interval: int = 30,
    ):
        """Initialize the aggregator.

        Args:
            peers: List of peer configurations with 'name', 'endpoint', 'site'
            timeout_seconds: Timeout for fetching peer readiness
            refresh_interval: How often to refresh cached data
        """
        self.peers = peers
        self.timeout_seconds = timeout_seconds
        self.refresh_interval = refresh_interval

        self._cache: dict[str, FederatedSite] = {}
        self._last_refresh: datetime | None = None
        self._running = False
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        """Start the aggregator."""
        logger.info("Starting federated capacity aggregator")
        self._running = True
        self._session = aiohttp.ClientSession()

        # Initial refresh
        await self.refresh()

        # Start refresh loop
        self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def stop(self) -> None:
        """Stop the aggregator."""
        logger.info("Stopping federated capacity aggregator")
        self._running = False

        if self._session:
            await self._session.close()

    async def refresh(self) -> None:
        """Refresh capacity data from all peers."""
        logger.debug("Refreshing federated capacity data")

        tasks = []
        for peer in self.peers:
            tasks.append(self._fetch_peer(peer))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for peer, result in zip(self.peers, results, strict=True):
            if isinstance(result, Exception):
                logger.error(f"Error fetching {peer['name']}: {result}")
                # Mark as unavailable
                self._cache[peer["name"]] = FederatedSite(
                    site_id=peer.get("site", "unknown"),
                    cluster_name=peer.get("name", "unknown"),
                    status=ReadinessStatus.UNAVAILABLE,
                    observed_at=datetime.utcnow(),
                    slurmctld_reachable=False,
                )
            elif isinstance(result, FederatedSite):
                self._cache[peer["name"]] = result

        self._last_refresh = datetime.utcnow()
        logger.debug(f"Refreshed {len(self._cache)} sites")

    async def _fetch_peer(self, peer: dict[str, Any]) -> FederatedSite | None:
        """Fetch readiness from a single peer.

        Args:
            peer: Peer configuration with 'endpoint' key

        Returns:
            FederatedSite or None if fetch failed
        """
        endpoint = peer["endpoint"]
        name = peer.get("name", "unknown")

        try:
            async with self._session.get(  # type: ignore[union-attr]
                f"{endpoint}/readiness",
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds),
            ) as response:
                if response.status != 200:
                    logger.warning(f"{name}: HTTP {response.status}")
                    return None

                data = await response.json()
                return self._parse_readiness(data, peer)

        except asyncio.TimeoutError:
            logger.warning(f"{name}: Timeout")
            return None
        except Exception as e:
            logger.warning(f"{name}: {e}")
            return None

    def _parse_readiness(self, data: dict[str, Any], peer: dict[str, Any]) -> FederatedSite:
        """Parse readiness message into FederatedSite.

        Args:
            data: Readiness message JSON
            peer: Peer configuration

        Returns:
            FederatedSite instance
        """
        signals = data.get("signals", {})
        capacity = data.get("capacity_hint", {})

        return FederatedSite(
            site_id=data.get("site_id", peer.get("site", "unknown")),
            cluster_name=data.get("cluster_name", peer.get("name", "unknown")),
            status=ReadinessStatus(data.get("status", "unknown")),
            observed_at=datetime.fromisoformat(data.get("observed_at", "").replace("Z", "+00:00")),
            idle_nodes=capacity.get("idle_nodes", 0),
            allocated_nodes=capacity.get("allocated_nodes", 0),
            pending_jobs=capacity.get("pending_jobs", 0),
            running_jobs=capacity.get("running_jobs", 0),
            slurmctld_reachable=signals.get("slurmctld_reachable", False),
            maintenance=signals.get("maintenance", False),
            ttl_seconds=data.get("ttl_seconds", 90),
        )

    async def _refresh_loop(self) -> None:
        """Background loop to refresh data periodically."""
        while self._running:
            await asyncio.sleep(self.refresh_interval)
            if self._running:
                await self.refresh()

    def query(self, query: CapacityQuery) -> CapacityResult:
        """Query aggregated capacity.

        Args:
            query: CapacityQuery with filters

        Returns:
            CapacityResult with matching sites
        """
        start_time = datetime.utcnow()

        matching_sites = []
        total_idle = 0
        total_allocated = 0

        for site in self._cache.values():
            # Apply filters
            if site.site_id in query.exclude_sites:
                continue

            if query.required_status and site.status != query.required_status:
                continue

            if site.idle_nodes < query.min_idle_nodes:
                continue

            if query.max_pending_jobs is not None and site.pending_jobs > query.max_pending_jobs:
                continue

            # TODO: Add GPU node filtering when available

            matching_sites.append(site)
            total_idle += site.idle_nodes
            total_allocated += site.allocated_nodes

        query_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        return CapacityResult(
            sites=matching_sites,
            total_idle_nodes=total_idle,
            total_allocated_nodes=total_allocated,
            query_time_ms=query_time,
            timestamp=datetime.utcnow(),
        )

    def get_all_sites(self) -> list[FederatedSite]:
        """Get all cached sites.

        Returns:
            List of FederatedSite instances
        """
        return list(self._cache.values())

    def is_fresh(self, max_age_seconds: int = 120) -> bool:
        """Check if cached data is fresh.

        Args:
            max_age_seconds: Maximum age in seconds

        Returns:
            True if data is fresh
        """
        if not self._last_refresh:
            return False

        age = (datetime.utcnow() - self._last_refresh).total_seconds()
        return age <= max_age_seconds
