"""Federated monitoring aggregator for EFP.

This module provides cross-site monitoring aggregation:
- Aggregates Prometheus metrics from all sites
- Provides /federated-health endpoint for EFP-wide health
- Cross-site alert correlation

Per EFP gap analysis:
- Each site has Prometheus/Grafana but no unified federated view
- EFP operators need a single pane of glass for all sites
- This component aggregates metrics and correlates alerts
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class SiteHealth:
    """Health status for a single site."""

    site_id: str
    status: str  # healthy, degraded, unhealthy
    last_seen: datetime | None
    metrics_available: bool
    alerts: list[str] = field(default_factory=list)
    latency_ms: float = 0.0


@dataclass
class FederatedHealth:
    """Aggregated health status for the federation."""

    timestamp: datetime
    total_sites: int
    healthy_sites: int
    degraded_sites: int
    unhealthy_sites: int
    sites: list[SiteHealth]
    cross_site_alerts: list[str] = field(default_factory=list)


class FederatedMonitor:
    """Aggregates monitoring data across EFP sites."""

    def __init__(
        self,
        peers: list[dict[str, Any]],
        scrape_interval: int = 30,
        timeout_seconds: int = 10,
    ):
        """Initialize the monitor.

        Args:
            peers: List of peer configurations with 'name', 'endpoint', 'site'
            scrape_interval: How often to scrape metrics (seconds)
            timeout_seconds: Timeout for each scrape
        """
        self.peers = peers
        self.scrape_interval = scrape_interval
        self.timeout_seconds = timeout_seconds

        self._site_health: dict[str, SiteHealth] = {}
        self._running = False
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        """Start the federated monitor."""
        logger.info("Starting federated monitor")
        self._running = True
        self._session = aiohttp.ClientSession()

        # Initial scrape
        await self.scrape_all()

        # Start scrape loop
        self._scrape_task = asyncio.create_task(self._scrape_loop())

    async def stop(self) -> None:
        """Stop the federated monitor."""
        logger.info("Stopping federated monitor")
        self._running = False

        if self._session:
            await self._session.close()

    async def scrape_all(self) -> FederatedHealth:
        """Scrape all sites and return aggregated health.

        Returns:
            FederatedHealth with current status
        """
        logger.debug("Scraping all sites")

        tasks = [self._scrape_peer(peer) for peer in self.peers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for peer, result in zip(self.peers, results, strict=True):
            site_name = peer.get("name", "unknown")

            if isinstance(result, Exception):
                logger.error(f"Error scraping {site_name}: {result}")
                self._site_health[site_name] = SiteHealth(
                    site_id=peer.get("site", "unknown"),
                    status="unhealthy",
                    last_seen=None,
                    metrics_available=False,
                    alerts=[f"Scrape failed: {result}"],
                )
            elif isinstance(result, SiteHealth):
                self._site_health[site_name] = result

        # Calculate aggregated health
        healthy = sum(1 for s in self._site_health.values() if s.status == "healthy")
        degraded = sum(1 for s in self._site_health.values() if s.status == "degraded")
        unhealthy = sum(1 for s in self._site_health.values() if s.status == "unhealthy")

        # Detect cross-site alerts
        alerts = self._detect_cross_site_alerts()

        return FederatedHealth(
            timestamp=datetime.utcnow(),
            total_sites=len(self._site_health),
            healthy_sites=healthy,
            degraded_sites=degraded,
            unhealthy_sites=unhealthy,
            sites=list(self._site_health.values()),
            cross_site_alerts=alerts,
        )

    async def _scrape_peer(self, peer: dict[str, Any]) -> SiteHealth | None:
        """Scrape a single peer's metrics.

        Args:
            peer: Peer configuration

        Returns:
            SiteHealth or None if scrape failed
        """
        endpoint = peer["endpoint"]
        site_name = peer.get("name", "unknown")
        site_id = peer.get("site", "unknown")

        start_time = datetime.utcnow()

        try:
            # Try to scrape /metrics endpoint
            async with self._session.get(  # type: ignore[union-attr]
                f"{endpoint}/metrics",
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds),
            ) as response:
                if response.status != 200:
                    logger.warning(f"{site_name}: HTTP {response.status}")
                    return SiteHealth(
                        site_id=site_id,
                        status="degraded",
                        last_seen=datetime.utcnow(),
                        metrics_available=False,
                        alerts=[f"HTTP {response.status}"],
                    )

                # Successfully scraped metrics
                latency = (datetime.utcnow() - start_time).total_seconds() * 1000

                return SiteHealth(
                    site_id=site_id,
                    status="healthy",
                    last_seen=datetime.utcnow(),
                    metrics_available=True,
                    latency_ms=latency,
                )

        except asyncio.TimeoutError:
            logger.warning(f"{site_name}: Timeout")
            return SiteHealth(
                site_id=site_id,
                status="unhealthy",
                last_seen=None,
                metrics_available=False,
                alerts=["Timeout"],
            )
        except Exception as e:
            logger.warning(f"{site_name}: {e}")
            return SiteHealth(
                site_id=site_id,
                status="unhealthy",
                last_seen=None,
                metrics_available=False,
                alerts=[str(e)],
            )

    async def _scrape_loop(self) -> None:
        """Background loop to scrape metrics periodically."""
        while self._running:
            await asyncio.sleep(self.scrape_interval)
            if self._running:
                await self.scrape_all()

    def _detect_cross_site_alerts(self) -> list[str]:
        """Detect alerts that affect multiple sites.

        Returns:
            List of cross-site alert messages
        """
        alerts = []

        # Check for widespread outages
        unhealthy_count = sum(1 for s in self._site_health.values() if s.status == "unhealthy")
        total_count = len(self._site_health)

        if total_count > 0 and unhealthy_count / total_count > 0.3:
            alerts.append(f"CRITICAL: {unhealthy_count}/{total_count} sites unhealthy")

        # Check for connectivity issues
        unreachable = [
            s.site_id for s in self._site_health.values() if not s.metrics_available
        ]
        if len(unreachable) > 3:
            alerts.append(f"WARNING: {len(unreachable)} sites unreachable")

        return alerts

    def get_health(self) -> FederatedHealth:
        """Get current aggregated health without scraping.

        Returns:
            FederatedHealth with cached data
        """
        healthy = sum(1 for s in self._site_health.values() if s.status == "healthy")
        degraded = sum(1 for s in self._site_health.values() if s.status == "degraded")
        unhealthy = sum(1 for s in self._site_health.values() if s.status == "unhealthy")

        alerts = self._detect_cross_site_alerts()

        return FederatedHealth(
            timestamp=datetime.utcnow(),
            total_sites=len(self._site_health),
            healthy_sites=healthy,
            degraded_sites=degraded,
            unhealthy_sites=unhealthy,
            sites=list(self._site_health.values()),
            cross_site_alerts=alerts,
        )
