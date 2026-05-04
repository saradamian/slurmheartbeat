"""Readiness publisher server for EFP federation.

Per EFP recommendation:
- Serve /readiness endpoint with signed readiness documents
- Serve /metrics endpoint with Prometheus-compatible telemetry
- Support mTLS for cross-site access
- Do not modify Slurm state (read-only)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from aiohttp import web

from slurmheartbeat.monitoring.metrics import MetricsServer

if TYPE_CHECKING:
    from slurmheartbeat.client.config import ServerConfig
    from slurmheartbeat.protocol.schema import ReadinessMessage

logger = logging.getLogger(__name__)


@dataclass
class ReadinessState:
    """State for readiness publisher."""

    site_id: str = "unknown"
    cluster_name: str = "unknown"
    fed_state: str = "UNKNOWN"
    maintenance: bool = False
    last_readiness: ReadinessMessage | None = None
    last_update: datetime | None = None


class ReadinessPublisher:
    """Readiness publisher serving /readiness and /metrics endpoints.

    Per EFP recommendation:
    - Serves signed JSON readiness documents
    - Does not modify Slurm state
    - Uses mTLS for authentication
    - Includes TTL for cache control
    """

    def __init__(
        self,
        config: ServerConfig,
        site_id: str,
        cluster_name: str,
        fed_state: str = "UNKNOWN",
        ttl_seconds: int = 90,
        metrics: MetricsServer | None = None,
        signing_key_file: str | None = None,
    ):
        """Initialize the readiness publisher.

        Args:
            config: Server configuration
            site_id: Unique site identifier
            cluster_name: Local cluster name
            fed_state: Federation state
            ttl_seconds: Time-to-live for readiness documents
            metrics: Optional metrics server instance (uses default if not provided)
            signing_key_file: Path to private key for signing readiness documents (optional)
        """
        self.config = config
        self.site_id = site_id
        self.cluster_name = cluster_name
        self.fed_state = fed_state
        self.ttl_seconds = ttl_seconds
        self.signing_key_file = signing_key_file

        self.state = ReadinessState(
            site_id=site_id,
            cluster_name=cluster_name,
            fed_state=fed_state,
        )

        # Use provided metrics or create default
        self._metrics = metrics if metrics else MetricsServer()
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._running = False

    @property
    def metrics(self) -> MetricsServer:
        """Get the metrics server instance."""
        return self._metrics

    async def start(self) -> None:
        """Start the readiness publisher server."""
        self._app = web.Application()

        # Add routes
        self._app.router.add_get("/readiness", self._handle_readiness)
        self._app.router.add_get("/metrics", self._handle_metrics)
        self._app.router.add_get("/health", self._handle_health)

        # Start metrics server
        await self._metrics.start()

        # Start HTTP server with TLS if configured
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        # Check if TLS is enabled
        tls_config = getattr(self.config, "tls", None)
        if tls_config and getattr(tls_config, "enabled", True):
            # Create SSL context
            from slurmheartbeat.protocol.security import create_ssl_context

            ssl_context = create_ssl_context(
                cert_file=tls_config.cert_file,
                key_file=tls_config.key_file,
                ca_file=tls_config.ca_file,
                client_auth=tls_config.client_auth,
            )

            self._site = web.TCPSite(
                self._runner,
                self.config.listen_address,
                self.config.listen_port,
                ssl_context=ssl_context,
            )
        else:
            # No TLS (for testing only)
            logger.warning("Starting without TLS - not recommended for production")
            self._site = web.TCPSite(
                self._runner,
                self.config.listen_address,
                self.config.listen_port,
            )

        await self._site.start()

        self._running = True
        logger.info(
            f"Readiness publisher started on {self.config.listen_address}:{self.config.listen_port}"
        )

    async def stop(self) -> None:
        """Stop the readiness publisher server."""
        self._running = False

        # Stop HTTP server
        if self._runner:
            await self._runner.cleanup()

        # Stop metrics server
        await self._metrics.stop()

        logger.info("Readiness publisher stopped")

    def update_readiness(self, readiness: ReadinessMessage) -> None:
        """Update the current readiness state.

        Args:
            readiness: New readiness message
        """
        self.state.last_readiness = readiness
        self.state.last_update = datetime.utcnow()
        self._metrics.record_readiness_update(readiness.status.value, self.site_id)
        logger.debug(f"Readiness updated: {readiness.status.value}")

    async def _handle_readiness(self, request: web.Request) -> web.Response:
        """Handle /readiness endpoint.

        Returns signed readiness document or error.

        Per EFP security:
        - Requires valid client certificate (mTLS)
        - Returns 403 if not authorized
        - Returns 503 if no readiness available
        """
        # Check for client certificate (mTLS)
        peer_name = self._extract_peer_name(request)

        if not peer_name:
            logger.warning("Readiness request without client certificate")
            return web.json_response(
                {"error": "Client certificate required"},
                status=403,
            )

        # Check authorization
        if not self._is_authorized(peer_name):
            logger.warning(f"Unauthorized readiness request from {peer_name}")
            return web.json_response(
                {"error": "Not authorized"},
                status=403,
            )

        # Check if readiness is available
        if not self.state.last_readiness:
            logger.warning("No readiness available")
            return web.json_response(
                {"error": "Readiness not available", "status": "unknown"},
                status=503,
            )

        # Check if readiness is expired
        if self.state.last_readiness.is_expired():
            logger.warning("Readiness expired")
            return web.json_response(
                {"error": "Readiness expired", "status": "unknown"},
                status=503,
            )

        # Return signed readiness document
        readiness = self.state.last_readiness
        
        # Sign the readiness document if signing is configured
        if self.signing_key_file and readiness.signature is None:
            try:
                from slurmheartbeat.protocol.security import load_private_key
                private_key = load_private_key(self.signing_key_file)
                # sign() accepts both key objects and PEM bytes
                readiness.sign(private_key)
                logger.debug("Readiness document signed")
            except Exception as e:
                logger.warning(f"Failed to sign readiness document: {e}")
                # Continue with unsigned document (fail-open for availability)
        
        return web.json_response(
            readiness.to_dict(),
            content_type="application/json",
        )

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """Handle /metrics endpoint for Prometheus.

        Returns Prometheus-compatible metrics.
        """
        metrics_text = self._metrics.get_metrics()
        return web.Response(
            text=metrics_text,
            content_type="text/plain",
        )

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Handle /health endpoint for liveness checks.

        Returns simple health status.
        """
        return web.json_response(
            {"status": "healthy", "running": self._running},
            content_type="application/json",
        )

    def _extract_peer_name(self, request: web.Request) -> str | None:
        """Extract peer name from client certificate.

        Per EFP security: Use mTLS client certificate for authentication.

        Args:
            request: aiohttp request

        Returns:
            Peer name (CN from certificate) or None
        """
        # Try to get peer certificate from transport
        try:
            transport = request.transport
            if not transport:
                return None

            # Try different keys for peer certificate
            cert = transport.get_extra_info("peercert")
            if not cert:
                cert = transport.get_extra_info("peer_certificate")

            if not cert:
                return None

            # Parse certificate to extract CN
            if isinstance(cert, dict):
                # Standard SSL dict format from getpeercert(binary_form=False)
                # Extract CN from subject
                subject = cert.get("subject", [])
                for attr_tuple in subject:
                    if attr_tuple and len(attr_tuple) >= 2:
                        key = (
                            attr_tuple[0][0]
                            if isinstance(attr_tuple[0], tuple)
                            else attr_tuple[0]
                        )
                        value = (
                            attr_tuple[0][1]
                            if isinstance(attr_tuple[0], tuple) and len(attr_tuple[0]) >= 2
                            else attr_tuple[1]
                            if len(attr_tuple) >= 2
                            else None
                        )
                        if key == "commonName":
                            return value
                return None
            elif isinstance(cert, bytes):
                # DER format (binary)
                from cryptography import x509

                cert = x509.load_der_x509_certificate(cert)

            # Extract CN from certificate
            if hasattr(cert, "subject"):
                for attr in cert.subject:
                    if attr.oid == x509.oid.NameOID.COMMON_NAME:
                        return attr.value

            return None
        except Exception as e:
            logger.error(f"Error extracting peer name: {e}")
            return None

    def _is_authorized(self, peer_name: str) -> bool:
        """Check if peer is authorized to access readiness.

        Per EFP security: Authorization is independent from signature verification.

        Args:
            peer_name: Peer name from certificate

        Returns:
            True if authorized, False otherwise
        """
        # Check against allowed sites from config
        allowed_sites = getattr(self.config, "allowed_sites", [])

        if not allowed_sites:
            # Fail closed: no allowed_sites configured means reject all
            # In production, this must be explicitly configured
            logger.error("No allowed_sites configured - rejecting all peers")
            return False

        return peer_name in allowed_sites


__all__ = ["ReadinessPublisher", "ReadinessState"]
