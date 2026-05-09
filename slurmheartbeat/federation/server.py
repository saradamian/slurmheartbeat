"""Federated capacity HTTP server for EFP.

This module provides HTTP endpoints for federated capacity discovery:
- GET /federated-capacity: Query aggregated capacity across all sites
- GET /federated-capacity/{site_id}: Get specific site details
- GET /federated-capacity/health: Health check

Per EFP gap analysis:
- No unified capacity discovery endpoint exists
- Researchers need to query "where can I run my job?"
- This provides a standardized API for capacity queries
"""

from __future__ import annotations

import logging
from datetime import datetime

from aiohttp import web
from slurmheartbeat.federation.aggregator import CapacityQuery, FederatedCapacityAggregator

logger = logging.getLogger(__name__)


class FederatedCapacityServer:
    """HTTP server for federated capacity discovery."""

    def __init__(self, aggregator: FederatedCapacityAggregator, port: int = 8444):
        """Initialize the server.

        Args:
            aggregator: FederatedCapacityAggregator instance
            port: HTTP server port
        """
        self.aggregator = aggregator
        self.port = port
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._running = False

    async def start(self) -> None:
        """Start the HTTP server."""
        logger.info(f"Starting federated capacity server on port {self.port}")

        self._app = web.Application()
        self._app.router.add_get("/federated-capacity", self._handle_capacity)
        self._app.router.add_get("/federated-capacity/health", self._handle_health)
        self._app.router.add_get("/federated-capacity/sites", self._handle_sites)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await self._site.start()

        self._running = True
        logger.info(f"Federated capacity server started on port {self.port}")

    async def stop(self) -> None:
        """Stop the HTTP server."""
        logger.info("Stopping federated capacity server")
        self._running = False

        if self._runner:
            await self._runner.cleanup()

    async def _handle_capacity(self, request: web.Request) -> web.Response:
        """Handle /federated-capacity endpoint.

        Query parameters:
        - min_idle_nodes: Minimum idle nodes required
        - max_pending_jobs: Maximum pending jobs allowed
        - required_status: Required status (ready, limited, etc.)
        - exclude_sites: Comma-separated sites to exclude
        """
        # Parse query parameters
        min_idle = int(request.query.get("min_idle_nodes", 0))
        max_pending = request.query.get("max_pending_jobs")
        required_status = request.query.get("required_status")
        exclude = request.query.get("exclude_sites", "").split(",")

        # Build query
        query = CapacityQuery(
            min_idle_nodes=min_idle,
            max_pending_jobs=int(max_pending) if max_pending else None,
            required_status=ReadinessStatus(required_status) if required_status else None,
            exclude_sites=[s for s in exclude if s],
        )

        # Execute query
        result = self.aggregator.query(query)

        # Build response
        response_data = {
            "timestamp": result.timestamp.isoformat(),
            "query_time_ms": result.query_time_ms,
            "total_idle_nodes": result.total_idle_nodes,
            "total_allocated_nodes": result.total_allocated_nodes,
            "matching_sites": len(result.sites),
            "sites": [
                {
                    "site_id": site.site_id,
                    "cluster_name": site.cluster_name,
                    "status": site.status.value,
                    "idle_nodes": site.idle_nodes,
                    "allocated_nodes": site.allocated_nodes,
                    "pending_jobs": site.pending_jobs,
                    "running_jobs": site.running_jobs,
                    "slurmctld_reachable": site.slurmctld_reachable,
                    "maintenance": site.maintenance,
                    "observed_at": site.observed_at.isoformat(),
                }
                for site in result.sites
            ],
        }

        return web.json_response(response_data)

    async def _handle_sites(self, request: web.Request) -> web.Response:
        """Handle /federated-capacity/sites endpoint.

        Returns all cached sites with their current status.
        """
        sites = self.aggregator.get_all_sites()

        response_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_sites": len(sites),
            "sites": [
                {
                    "site_id": site.site_id,
                    "cluster_name": site.cluster_name,
                    "status": site.status.value,
                    "idle_nodes": site.idle_nodes,
                    "allocated_nodes": site.allocated_nodes,
                    "pending_jobs": site.pending_jobs,
                    "running_jobs": site.running_jobs,
                    "slurmctld_reachable": site.slurmctld_reachable,
                    "maintenance": site.maintenance,
                    "observed_at": site.observed_at.isoformat(),
                }
                for site in sites
            ],
        }

        return web.json_response(response_data)

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Handle /federated-capacity/health endpoint."""
        is_fresh = self.aggregator.is_fresh()
        last_refresh = self.aggregator._last_refresh.isoformat() if self.aggregator._last_refresh else None

        response_data = {
            "status": "healthy" if is_fresh else "stale",
            "running": self._running,
            "last_refresh": last_refresh,
            "sites_cached": len(self.aggregator._cache),
        }

        status_code = 200 if is_fresh else 503
        return web.json_response(response_data, status=status_code)


# Import here to avoid circular dependency (ReadinessStatus used in type hints)
from slurmheartbeat.protocol.schema import ReadinessStatus  # noqa: E402
