"""Heartbeat sender for federation peers."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from slurmheartbeat.client.config import HeartbeatClientConfig, PeerConfig
    from slurmheartbeat.protocol.message import HeartbeatMessage

logger = logging.getLogger(__name__)


@dataclass
class SendResult:
    """Result of a heartbeat send operation."""

    success: bool
    peer_name: str
    latency_ms: float
    error: str | None = None


class HeartbeatSender:
    """Sends heartbeat messages to federation peers."""

    def __init__(self, config: HeartbeatClientConfig):
        """Initialize the heartbeat sender.

        Args:
            config: Client configuration with peer list.
        """
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._timeout = httpx.Timeout(config.timeout_seconds, connect=5.0)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with TLS support."""
        if self._client is None or self._client.is_closed:
            # For now, no TLS configuration for outgoing requests
            # TLS can be added later if needed for peer-to-peer communication
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
            )

        return self._client

    async def send(self, peer: PeerConfig, message: HeartbeatMessage) -> SendResult:
        """Send heartbeat message to a peer.

        Args:
            peer: Peer configuration.
            message: Heartbeat message to send.

        Returns:
            SendResult with success status and latency.
        """
        import time

        start_time = time.time()

        try:
            client = await self._get_client()

            # Prepare request
            headers = {"Content-Type": "application/json"}

            # Send heartbeat
            response = await client.post(
                peer.endpoint,
                json=message.to_dict(),
                headers=headers,
            )

            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                logger.debug(f"Heartbeat sent to {peer.name} in {latency_ms:.2f}ms")
                return SendResult(
                    success=True,
                    peer_name=peer.name,
                    latency_ms=latency_ms,
                )
            else:
                logger.warning(
                    f"Failed to send heartbeat to {peer.name}: HTTP {response.status_code}"
                )
                return SendResult(
                    success=False,
                    peer_name=peer.name,
                    latency_ms=latency_ms,
                    error=f"HTTP {response.status_code}: {response.text}",
                )

        except httpx.TimeoutException as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.warning(f"Timeout sending heartbeat to {peer.name}: {e}")
            return SendResult(
                success=False,
                peer_name=peer.name,
                latency_ms=latency_ms,
                error=f"Timeout: {e}",
            )

        except httpx.ConnectError as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.warning(f"Connection error sending heartbeat to {peer.name}: {e}")
            return SendResult(
                success=False,
                peer_name=peer.name,
                latency_ms=latency_ms,
                error=f"Connection error: {e}",
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Error sending heartbeat to {peer.name}: {e}")
            return SendResult(
                success=False,
                peer_name=peer.name,
                latency_ms=latency_ms,
                error=str(e),
            )

    async def send_with_retry(
        self, peer: PeerConfig, message: HeartbeatMessage, max_retries: int | None = None
    ) -> SendResult:
        """Send heartbeat with retry logic.

        Args:
            peer: Peer configuration.
            message: Heartbeat message to send.
            max_retries: Maximum retry attempts (default: config.retry_count).

        Returns:
            SendResult with success status.
        """
        max_retries = max_retries or self.config.retry_count
        backoff = self.config.retry_backoff

        for attempt in range(max_retries + 1):
            result = await self.send(peer, message)

            if result.success:
                return result

            if attempt < max_retries:
                wait_time = backoff**attempt
                logger.debug(f"Retrying heartbeat to {peer.name} in {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

        return result

    async def send_to_all(self, message: HeartbeatMessage) -> list[SendResult]:
        """Send heartbeat to all configured peers.

        Args:
            message: Heartbeat message to send.

        Returns:
            List of SendResult for each peer.
        """
        if not self.config.federation or not self.config.federation.peers:
            logger.warning("No federation peers configured")
            return []

        # Send to all peers in parallel
        tasks = [self.send_with_retry(peer, message) for peer in self.config.federation.peers]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed_results = []
        for peer, result in zip(self.config.federation.peers, results, strict=True):
            if isinstance(result, Exception):
                processed_results.append(
                    SendResult(
                        success=False,
                        peer_name=peer.name,
                        latency_ms=0,
                        error=str(result),
                    )
                )
            else:
                processed_results.append(result)

        # Log summary
        success_count = sum(1 for r in processed_results if r.success)
        total_count = len(processed_results)

        if success_count < total_count:
            logger.warning(f"Heartbeat: {success_count}/{total_count} peers reached")

        return processed_results

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


__all__ = ["HeartbeatSender", "SendResult"]
