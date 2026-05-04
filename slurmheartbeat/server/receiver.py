"""Heartbeat receiver server for federation peers."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from aiohttp import web

from slurmheartbeat.protocol.message import HeartbeatMessage

if TYPE_CHECKING:
    from slurmheartbeat.client.config import ServerConfig

logger = logging.getLogger(__name__)


@dataclass
class PeerState:
    """State of a federation peer."""

    name: str
    last_seen: datetime | None = None
    status: str = "unknown"  # unknown, healthy, degraded, unhealthy
    consecutive_failures: int = 0
    last_latency_ms: float = 0.0
    error: str | None = None


class FederationState:
    """Manages federation peer states."""

    def __init__(self, config: ServerConfig):
        """Initialize federation state.

        Args:
            config: Server configuration.
        """
        self.config = config
        self._peers: dict[str, PeerState] = {}
        self._lock = asyncio.Lock()

        # Thresholds
        self.healthy_threshold = 2
        self.degraded_threshold = 2
        self.down_threshold = 3

        # Allowed federation members (CN or OU from certificates)
        # Initialize from config if available
        self._allowed_members: set[str] = set()
        if hasattr(config, "allowed_sites") and config.allowed_sites:
            self._allowed_members = set(config.allowed_sites)

        # Peer public keys for signature verification (peer_name -> public_key_pem)
        self._peer_public_keys: dict[str, str] = {}

        # Rate limiting
        self._request_counts: dict[str, list[float]] = {}
        self._rate_limit_window = 60  # seconds
        self._rate_limit_max_requests = 100  # per window

    async def update_peer(
        self, peer_name: str, message: HeartbeatMessage, latency_ms: float
    ) -> PeerState:
        """Update peer state based on received heartbeat.

        Args:
            peer_name: Name of the peer.
            message: Received heartbeat message.
            latency_ms: Latency of the heartbeat.

        Returns:
            Updated PeerState.
        """
        async with self._lock:
            if peer_name not in self._peers:
                self._peers[peer_name] = PeerState(name=peer_name)

            peer = self._peers[peer_name]
            peer.last_seen = datetime.utcnow()
            peer.status = message.status
            peer.last_latency_ms = latency_ms
            peer.consecutive_failures = 0
            peer.error = None

            return peer

    async def record_failure(self, peer_name: str, error: str) -> PeerState:
        """Record a failed heartbeat from a peer.

        Args:
            peer_name: Name of the peer.
            error: Error message.

        Returns:
            Updated PeerState.
        """
        async with self._lock:
            if peer_name not in self._peers:
                self._peers[peer_name] = PeerState(name=peer_name)

            peer = self._peers[peer_name]
            peer.consecutive_failures += 1
            peer.error = error

            # Update status based on failures
            if peer.consecutive_failures >= self.down_threshold:
                peer.status = "unhealthy"
            elif peer.consecutive_failures >= self.degraded_threshold:
                peer.status = "degraded"

            return peer

    async def get_peer(self, peer_name: str) -> PeerState | None:
        """Get state for a specific peer.

        Args:
            peer_name: Name of the peer.

        Returns:
            PeerState or None if not found.
        """
        async with self._lock:
            return self._peers.get(peer_name)

    async def get_all_peers(self) -> list[PeerState]:
        """Get state for all peers.

        Returns:
            List of all PeerState objects.
        """
        async with self._lock:
            return list(self._peers.values())

    async def get_healthy_peers(self) -> list[PeerState]:
        """Get all healthy peers.

        Returns:
            List of PeerState with status "healthy".
        """
        async with self._lock:
            return [p for p in self._peers.values() if p.status == "healthy"]

    def set_allowed_members(self, members: list[str]) -> None:
        """Set the list of allowed federation members.

        Args:
            members: List of allowed member names (CN or OU from certificates).
        """
        self._allowed_members = set(members)

    def is_member_allowed(self, member_name: str) -> bool:
        """Check if a member is allowed to send heartbeats.

        Args:
            member_name: Name of the member to check.

        Returns:
            True if allowed, False otherwise.
        """
        if not self._allowed_members:
            # If no allowed members set, allow all (backward compatibility)
            return True
        return member_name in self._allowed_members

    def set_peer_public_key(self, peer_name: str, public_key_pem: str) -> None:
        """Store public key for a federation peer.

        Args:
            peer_name: Name of the peer.
            public_key_pem: Public key in PEM format.
        """
        self._peer_public_keys[peer_name] = public_key_pem

    def get_peer_public_key(self, peer_name: str) -> str | None:
        """Get public key for a peer.

        Args:
            peer_name: Name of the peer.

        Returns:
            Public key in PEM format, or None if not found.
        """
        return self._peer_public_keys.get(peer_name)

    def check_rate_limit(self, client_ip: str) -> bool:
        """Check if a client is within rate limits.

        Args:
            client_ip: Client IP address (or X-Forwarded-For if behind proxy).

        Returns:
            True if within limits, False if rate limited.
        """
        import time

        now = time.time()

        # Clean old entries
        window_start = now - self._rate_limit_window

        if client_ip not in self._request_counts:
            self._request_counts[client_ip] = []

        # Remove old timestamps
        self._request_counts[client_ip] = [
            ts for ts in self._request_counts[client_ip] if ts > window_start
        ]

        # Check if over limit
        if len(self._request_counts[client_ip]) >= self._rate_limit_max_requests:
            return False

        # Record this request
        self._request_counts[client_ip].append(now)
        return True


class HeartbeatReceiver:
    """Receives heartbeat messages from federation peers."""

    def __init__(self, config: ServerConfig):
        """Initialize the heartbeat receiver.

        Args:
            config: Server configuration.
        """
        self.config = config
        self.state = FederationState(config)
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._running = False

        # Load allowed members from ServerConfig.allowed_sites
        # and peer public keys from ServerConfig.peer_public_keys
        if hasattr(config, "allowed_sites") and config.allowed_sites:
            self.state.set_allowed_members(config.allowed_sites)

        # Load peer public keys from server config if available
        if hasattr(config, "peer_public_keys") and config.peer_public_keys:
            peer_public_keys = getattr(config, "peer_public_keys", {})
            for peer_name, public_key_pem in peer_public_keys.items():
                self.state.set_peer_public_key(peer_name, public_key_pem)

    async def _handle_heartbeat(self, request: web.Request) -> web.Response:
        """Handle incoming heartbeat request.

        Args:
            request: HTTP request.

        Returns:
            HTTP response.
        """
        import time

        start_time = time.time()

        try:
            # Get client IP for rate limiting (check X-Forwarded-For if behind proxy)
            client_ip = request.remote
            if not client_ip:
                client_ip = "unknown"
            elif "X-Forwarded-For" in request.headers:
                # Use the first IP in X-Forwarded-For (original client)
                forwarded_for = request.headers["X-Forwarded-For"].split(",")[0].strip()
                if forwarded_for:
                    client_ip = forwarded_for

            # Check rate limit
            if not self.state.check_rate_limit(client_ip):
                logger.warning(f"Rate limit exceeded for {client_ip}")
                return web.json_response({"error": "Rate limit exceeded"}, status=429)

            # Extract client certificate info if TLS is enabled
            peer_name = None
            if request.transport:
                # Try peercert first (standard asyncio SSL transport)
                cert = request.transport.get_extra_info("peercert")
                if not cert:
                    # Fallback to ssl_object
                    ssl_obj = request.transport.get_extra_info("ssl_object")
                    if ssl_obj:
                        cert = ssl_obj.getpeercert(binary_form=False)

                if cert and isinstance(cert, dict):
                    # Extract CN from certificate using shared helper
                    subject = cert.get("subject", [])
                    peer_name = self._extract_cn_from_subject(subject)

            # Parse JSON body
            try:
                data = await request.json()
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in heartbeat request: {e}")
                return web.json_response({"error": "Invalid JSON"}, status=400)

            # Validate and parse message
            try:
                message = HeartbeatMessage.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to parse heartbeat message: {e}")
                return web.json_response({"error": "Invalid message format"}, status=400)

            # Extract peer name from certificate ONLY - no query param fallback
            if not peer_name:
                logger.warning("No client certificate provided - rejecting request")
                return web.json_response({"error": "Client certificate required"}, status=403)

            # Check authorization
            if not self.state.is_member_allowed(peer_name):
                logger.warning(f"Unauthorized heartbeat from {peer_name}")
                return web.json_response({"error": "Unauthorized"}, status=403)

            # Verify message signature if present
            if message.signature:
                # Get public key from peer store
                public_key_pem = self.state.get_peer_public_key(peer_name)

                if not public_key_pem:
                    logger.error(
                        f"Cannot verify signature for {peer_name}: no public key configured"
                    )
                    return web.json_response({"error": "Signature verification failed"}, status=403)

                # Verify signature - fail closed on any error
                try:
                    if not message.verify_signature(public_key_pem.encode()):
                        logger.error(f"Invalid signature from {peer_name}")
                        return web.json_response({"error": "Invalid signature"}, status=403)
                except Exception as e:
                    logger.error(
                        f"Signature verification failed for {peer_name}: {type(e).__name__}"
                    )
                    return web.json_response({"error": "Signature verification failed"}, status=403)

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Update state
            await self.state.update_peer(peer_name, message, latency_ms)

            logger.debug(f"Heartbeat received from {peer_name} in {latency_ms:.2f}ms")

            return web.json_response({"status": "ok", "latency_ms": latency_ms}, status=200)

        except web.HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            logger.error(f"Error handling heartbeat: {e}")
            return web.json_response({"error": "Internal server error"}, status=500)

    def _extract_cn_from_subject(self, subject: list) -> str | None:
        """Extract commonName from certificate subject, handling nested RDN format.

        Args:
            subject: Subject from getpeercert(), can be nested RDN tuples

        Returns:
            CN value or None
        """
        # Handle nested RDN format: ((("commonName", "value"),), (("organizationName", "value"),),)
        # Each RDN is a tuple of attribute tuples
        for rdn in subject:
            # rdn can be:
            # 1. Nested: (("commonName", "value"),) - tuple of attribute tuples
            # 2. Flattened: ("commonName", "value") - single attribute tuple
            if isinstance(rdn, tuple):
                # Check if this is a nested RDN (tuple of tuples)
                if len(rdn) > 0 and isinstance(rdn[0], tuple):
                    # Nested format: iterate through attributes in this RDN
                    for attr in rdn:
                        if isinstance(attr, tuple) and len(attr) >= 2:
                            key, value = attr[0], attr[1]
                            if key == "commonName":
                                return value
                else:
                    # Flattened format: rdn itself is ("commonName", "value")
                    if len(rdn) >= 2 and rdn[0] == "commonName":
                        return rdn[1]
        return None

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Handle health check request.

        Args:
            request: HTTP request.

        Returns:
            HTTP response.
        """
        return web.json_response({"status": "healthy", "peers": len(self.state._peers)}, status=200)

    async def _handle_peers(self, request: web.Request) -> web.Response:
        """Handle peer status request.

        Args:
            request: HTTP request.

        Returns:
            HTTP response.
        """
        peers = await self.state.get_all_peers()
        return web.json_response(
            {
                "peers": [
                    {
                        "name": p.name,
                        "status": p.status,
                        "last_seen": p.last_seen.isoformat() if p.last_seen else None,
                        "consecutive_failures": p.consecutive_failures,
                        "last_latency_ms": p.last_latency_ms,
                        "error": p.error,
                    }
                    for p in peers
                ]
            },
            status=200,
        )

    async def start(self) -> None:
        """Start the heartbeat receiver server."""
        logger.info(
            f"Starting heartbeat receiver on {self.config.listen_address}:{self.config.listen_port}"
        )

        # Create web application
        self._app = web.Application()
        self._app.router.add_post("/heartbeat", self._handle_heartbeat)
        self._app.router.add_get("/health", self._handle_health)
        self._app.router.add_get("/peers", self._handle_peers)

        # Setup TLS if enabled
        ssl_context = None
        if self.config.tls and self.config.tls.enabled:
            try:
                from slurmheartbeat.protocol.security import create_ssl_context

                ssl_context = create_ssl_context(
                    cert_file=self.config.tls.cert_file,
                    key_file=self.config.tls.key_file,
                    ca_file=self.config.tls.ca_file
                    if self.config.tls.client_auth == "required"
                    else None,
                    client_auth=self.config.tls.client_auth,
                    min_version=self.config.tls.min_version,
                    max_version=self.config.tls.max_version,
                )
                logger.info("TLS enabled for heartbeat receiver")
            except Exception as e:
                logger.error(f"Failed to setup TLS: {e}")
                raise

        # Start runner
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(
            self._runner,
            self.config.listen_address,
            self.config.listen_port,
            ssl_context=ssl_context,
        )

        await self._site.start()
        self._running = True

        logger.info(
            f"Heartbeat receiver started on {self.config.listen_address}:{self.config.listen_port}"
        )

    async def stop(self) -> None:
        """Stop the heartbeat receiver server."""
        if not self._running:
            return

        logger.info("Stopping heartbeat receiver")
        self._running = False

        if self._runner:
            await self._runner.cleanup()

        logger.info("Heartbeat receiver stopped")

    async def get_state(self) -> dict:
        """Get current federation state.

        Returns:
            Dictionary with peer states.
        """
        peers = await self.state.get_all_peers()
        return {
            "peers": [
                {
                    "name": p.name,
                    "status": p.status,
                    "last_seen": p.last_seen.isoformat() if p.last_seen else None,
                    "consecutive_failures": p.consecutive_failures,
                    "last_latency_ms": p.last_latency_ms,
                    "error": p.error,
                }
                for p in peers
            ]
        }


__all__ = ["FederationState", "HeartbeatReceiver", "PeerState"]
