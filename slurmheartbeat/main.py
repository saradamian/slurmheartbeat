#!/usr/bin/env python3
"""Slurm Heartbeat daemon entry point with EFP readiness publisher support.

This module provides the main entry point for the Slurm Heartbeat daemon,
which monitors the health of Slurm clusters within the European Federated Platform (EFP).

Per EFP recommendation:
- Support both client mode (sending heartbeats) and publisher mode (serving readiness)
- Readiness publisher serves /readiness and /metrics endpoints
- Client sends signed heartbeats to federation peers
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from slurmheartbeat.client.collector import SlurmCollector
from slurmheartbeat.client.config import ClientConfig
from slurmheartbeat.client.normalizer import ReadinessNormalizer
from slurmheartbeat.client.sender import HeartbeatSender
from slurmheartbeat.monitoring.metrics import MetricsServer
from slurmheartbeat.server.publisher import ReadinessPublisher
from slurmheartbeat.server.receiver import HeartbeatReceiver

logger = logging.getLogger(__name__)


class HeartbeatDaemon:
    """Main heartbeat daemon that coordinates client and server components.

    Per EFP recommendation:
    - Support both client mode (sending heartbeats) and publisher mode (serving readiness)
    - Publisher mode serves /readiness and /metrics endpoints
    - Client mode sends signed heartbeats to federation peers
    """

    def __init__(self, config_path: str, mode: str = "both"):
        """Initialize the heartbeat daemon.

        Args:
            config_path: Path to the configuration file.
            mode: Operation mode - "client", "publisher", or "both"
        """
        self.config_path = Path(config_path)
        self.config = ClientConfig.load(self.config_path)
        self.mode = mode

        # Client components
        self.collector: SlurmCollector | None = None
        self.sender: HeartbeatSender | None = None
        self.normalizer: ReadinessNormalizer | None = None

        # Server components
        self.receiver: HeartbeatReceiver | None = None
        self.publisher: ReadinessPublisher | None = None

        # Monitoring
        self.metrics: MetricsServer | None = None
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start the heartbeat daemon."""
        logger.info("Starting Slurm Heartbeat daemon")
        self._running = True

        # Initialize metrics server FIRST, before any components that depend on it
        # This ensures configured metrics are used instead of default singleton
        if self.config.monitoring.prometheus.enabled:
            self.metrics = MetricsServer(self.config.monitoring.prometheus)
            # Note: Metrics HTTP server is NOT started here - publisher serves /metrics endpoint
            logger.info(f"Prometheus metrics available at port {self.config.monitoring.prometheus.port}")

        # Initialize components based on mode
        # In publisher mode, we still need collector/normalizer to generate readiness
        # client.enabled only controls outgoing heartbeat sending, not readiness generation
        if self.mode in ("client", "both", "publisher"):
            # Always initialize collector/normalizer for readiness generation
            self.collector = SlurmCollector(self.config.client.slurm)
            self.normalizer = ReadinessNormalizer(
                site_id=self.config.cluster.id,
                cluster_name=self.config.cluster.name,
                fed_state="UNKNOWN",  # Will be updated from Slurm
                ttl_seconds=90,
            )

            # Only initialize sender if client is enabled
            if self.config.client.enabled:
                self.sender = HeartbeatSender(self.config.client) if self.mode in ("client", "both") else None
            else:
                logger.info("Client heartbeat disabled (outgoing heartbeats)")

        if self.mode in ("publisher", "both") and self.config.server.enabled:
            # Pass shared metrics instance to publisher (may be None if prometheus disabled)
            # Also pass signing_key_file from server config and prometheus config
            self.publisher = ReadinessPublisher(
                config=self.config.server,
                site_id=self.config.cluster.id,
                cluster_name=self.config.cluster.name,
                fed_state="UNKNOWN",
                ttl_seconds=90,
                metrics=self.metrics,  # Pass shared metrics instance (or None)
                signing_key_file=self.config.server.signing_key_file,
                prometheus_config=self.config.monitoring.prometheus,
            )

        # Only start legacy P2P receiver if explicitly enabled (feature flag)
        if (
            self.mode == "both"
            and self.config.server.enabled
            and getattr(self.config.server, "enable_legacy_p2p", False)
        ):
            self.receiver = HeartbeatReceiver(self.config.server)

        # Start components (publisher starts its own HTTP server, metrics already started above)
        if self.receiver:
            await self.receiver.start()
            logger.info(
                f"Heartbeat server started on {self.config.server.listen_address}:{self.config.server.listen_port}"
            )

        if self.publisher:
            await self.publisher.start()
            logger.info(
                f"Readiness publisher started on {self.config.server.listen_address}:{self.config.server.listen_port}"
            )

        # Update peer status metrics on startup
        if self.metrics and self.receiver:
            state = await self.receiver.get_state()
            for peer_data in state.get("peers", []):
                peer_name = peer_data.get("name", "unknown")
                status = peer_data.get("status", "unknown")
                failures = peer_data.get("consecutive_failures", 0)
                self.metrics.update_peer_status(peer_name, status, 0, failures)

        # Start heartbeat loop for readiness generation and/or outgoing heartbeats
        # client.enabled only controls outgoing heartbeat sending, NOT readiness generation
        if self.mode in ("client", "both", "publisher"):
            # Always start the loop for readiness generation in publisher mode
            # client.enabled only gates the HeartbeatSender (outgoing heartbeats)
            self._tasks.append(asyncio.create_task(self._heartbeat_loop()))
            if not self.config.client.enabled:
                logger.info("Outgoing heartbeats disabled (client.enabled=false), but readiness generation continues")

        logger.info("Slurm Heartbeat daemon started successfully")

    async def stop(self) -> None:
        """Stop the heartbeat daemon."""
        logger.info("Stopping Slurm Heartbeat daemon")
        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Stop components
        if self.receiver:
            await self.receiver.stop()

        if self.publisher:
            await self.publisher.stop()

        if self.metrics:
            await self.metrics.stop()

        logger.info("Slurm Heartbeat daemon stopped")

    async def _heartbeat_loop(self) -> None:
        """Main heartbeat loop that collects and sends metrics.

        Per EFP recommendation:
        - Collect local Slurm state
        - Normalize to readiness schema
        - Publish readiness (if publisher mode)
        - Send signed heartbeats to peers (if client mode)
        """
        while self._running:
            try:
                # Collect metrics from Slurm (single collection per loop)
                if self.collector:
                    metrics = await self.collector.collect()

                    # Derive slurmctld_reachable from collection success
                    # Use the collect_success flag from the collector
                    slurmctld_reachable = metrics.collect_success if metrics else False
                    maintenance = await self._check_maintenance_state()

                    # Normalize to EFP readiness schema
                    if self.normalizer:
                        readiness = self.normalizer.normalize(
                            metrics,
                            slurmctld_reachable=slurmctld_reachable,
                            maintenance=maintenance,
                        )

                        # Update readiness in publisher
                        if self.publisher:
                            self.publisher.update_readiness(readiness)

                        # Update Prometheus metrics
                        if self.metrics:
                            self.metrics.update_local_metrics(
                                node_total=metrics.node_stats.total,
                                node_idle=metrics.node_stats.idle,
                                node_allocated=metrics.node_stats.allocated,
                                node_drained=metrics.node_stats.drained,
                                node_down=metrics.node_stats.down,
                                jobs_pending=metrics.job_stats.pending,
                                jobs_running=metrics.job_stats.running,
                                jobs_failed=metrics.job_stats.failed,
                                cpu_percent=metrics.resource_usage.cpu_percent,
                                memory_percent=metrics.resource_usage.memory_percent,
                                gpu_percent=metrics.resource_usage.gpu_percent,
                            )

                    # Create legacy heartbeat message for backward compatibility
                    from slurmheartbeat.protocol.message import ClusterInfo, HeartbeatMessage

                    cluster_info = ClusterInfo(
                        id=self.config.cluster.id,
                        name=self.config.cluster.name,
                        site=self.config.cluster.site,
                    )
                    message = HeartbeatMessage.from_metrics(metrics, cluster_info)

                    # Send to all peers
                    if self.sender:
                        results = await self.sender.send_to_all(message)

                        # Update metrics if available
                        if self.metrics:
                            for result in results:
                                if result.success:
                                    self.metrics.record_heartbeat_sent(result.peer_name)
                                    self.metrics.record_heartbeat_latency(
                                        result.peer_name, result.latency_ms / 1000
                                    )
                                else:
                                    self.metrics.record_heartbeat_error(
                                        result.peer_name,
                                        "timeout"
                                        if "timeout" in result.error.lower()
                                        else "connection",
                                    )

                # Wait for next interval
                await asyncio.sleep(self.config.client.interval_seconds)

                # Update peer status metrics
                if self.metrics and self.receiver:
                    state = await self.receiver.get_state()
                    for peer_data in state.get("peers", []):
                        peer_name = peer_data.get("name", "unknown")
                        status = peer_data.get("status", "unknown")
                        last_seen = peer_data.get("last_seen")
                        failures = peer_data.get("consecutive_failures", 0)

                        # Calculate seconds since last seen
                        last_seen_seconds = 0
                        if last_seen:
                            try:
                                from datetime import datetime

                                last_seen_dt = datetime.fromisoformat(
                                    last_seen.replace("Z", "+00:00")
                                )
                                last_seen_seconds = (
                                    datetime.utcnow() - last_seen_dt.replace(tzinfo=None)
                                ).total_seconds()
                            except Exception:
                                last_seen_seconds = 0

                        self.metrics.update_peer_status(
                            peer_name, status, last_seen_seconds, failures
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(self.config.client.interval_seconds)

    async def _check_slurmctld_reachable(self) -> bool:
        """Check if slurmctld is reachable.

        Returns:
            True if slurmctld is reachable, False otherwise.
        """
        if not self.collector:
            return False

        try:
            # Try to collect metrics - if successful, slurmctld is reachable
            await self.collector.collect()
            return True
        except Exception:
            return False

    async def _check_maintenance_state(self) -> bool:
        """Check if the system is in maintenance mode.

        Returns:
            True if in maintenance mode, False otherwise.
        """
        # Check for maintenance file using configurable path
        # Note: Simple file existence check doesn't block event loop
        maintenance_path = getattr(self.config.server, "maintenance_path", "/var/run/slurm/heartbeat/maintenance")
        maintenance_file = Path(maintenance_path)
        try:
            return maintenance_file.exists()
        except Exception:
            return False


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Slurm Heartbeat Daemon")
    parser.add_argument(
        "-c",
        "--config",
        default="/etc/slurm/heartbeat/config.yaml",
        help="Path to configuration file",
    )
    parser.add_argument(
        "-m",
        "--mode",
        choices=["client", "publisher", "both"],
        default="both",
        help="Operation mode: client (send heartbeats), publisher (serve readiness), or both",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    return parser.parse_args()


def setup_logging(verbose: bool) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def main() -> int:
    """Main entry point."""
    args = parse_args()
    setup_logging(args.verbose)

    daemon = HeartbeatDaemon(args.config, mode=args.mode)

    # Setup signal handlers
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("Received shutdown signal")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await daemon.start()

        # Keep running until stopped
        await shutdown_event.wait()

    except Exception as e:
        logger.error(f"Daemon error: {e}")
        return 1
    finally:
        await daemon.stop()

    return 0


def run() -> None:
    """Sync wrapper for console script entry point."""
    sys.exit(asyncio.run(main()))


if __name__ == "__main__":
    run()
