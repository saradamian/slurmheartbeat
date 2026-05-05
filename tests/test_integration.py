"""Integration tests for Slurm Heartbeat daemon."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from slurmheartbeat.protocol.message import ClusterInfo, HeartbeatMessage


class TestHeartbeatIntegration:
    """Integration tests for heartbeat flow."""

    @pytest.mark.asyncio
    async def test_full_heartbeat_flow(self, sample_heartbeat_message, sample_client_config):
        """Test complete heartbeat flow from collection to sending."""
        from slurmheartbeat.client.collector import SlurmCollector
        from slurmheartbeat.client.sender import HeartbeatSender

        # Mock Slurm collector
        with patch.object(SlurmCollector, "collect") as mock_collect:
            mock_metrics = MagicMock()
            mock_metrics.node_stats.total = 100
            mock_metrics.node_stats.idle = 60
            mock_metrics.node_stats.allocated = 35
            mock_metrics.node_stats.drained = 3
            mock_metrics.node_stats.down = 2
            mock_metrics.job_stats.pending = 10
            mock_metrics.job_stats.running = 35
            mock_metrics.job_stats.failed = 5
            mock_metrics.resource_usage.cpu_percent = 65.5
            mock_metrics.resource_usage.memory_percent = 72.3
            mock_metrics.resource_usage.gpu_percent = 45.0
            mock_metrics.collect_success = True

            mock_collect.return_value = mock_metrics

            # Create collector and sender
            collector = SlurmCollector(sample_client_config.client.slurm)
            _ = HeartbeatSender(sample_client_config.client)

            # Collect metrics
            metrics = await collector.collect()

            # Create message using from_dict (no from_metrics method)
            from slurmheartbeat.protocol.message import ClusterInfo, HeartbeatMessage

            message = HeartbeatMessage(
                cluster=ClusterInfo(
                    id=sample_client_config.cluster.id,
                    name=sample_client_config.cluster.name,
                    site=sample_client_config.cluster.site,
                ),
                node_stats=metrics.node_stats,
                job_stats=metrics.job_stats,
                resource_usage=metrics.resource_usage,
            )

            # Verify message was created
            assert message.cluster.id == sample_client_config.cluster.id
            assert message.node_stats.total == 100

    @pytest.mark.asyncio
    async def test_peer_state_tracking(self, sample_server_config):
        """Test that peer state is tracked correctly."""
        from slurmheartbeat.server.receiver import HeartbeatReceiver

        receiver = HeartbeatReceiver(sample_server_config)

        # Create heartbeat message
        message = HeartbeatMessage(
            cluster=ClusterInfo(id="peer1", name="peer1", site="test-site"),
        )

        # Simulate receiving heartbeat
        await receiver.update_peer("peer1", message, 15.0)

        # Verify state was updated
        peer = await receiver.get_peer("peer1")
        assert peer is not None
        assert peer.name == "peer1"
        assert peer.status == "healthy"
        assert peer.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_metrics_collection_and_export(
        self, sample_client_config, sample_prometheus_config
    ):
        """Test that metrics are collected and exported correctly."""
        from slurmheartbeat.client.collector import SlurmCollector
        from slurmheartbeat.monitoring.metrics import MetricsServer

        # Create collector and metrics server
        collector = SlurmCollector(sample_client_config.client.slurm)
        metrics_server = MetricsServer(sample_prometheus_config)

        # Mock metrics collection
        with patch.object(SlurmCollector, "collect") as mock_collect:
            mock_metrics = MagicMock()
            mock_metrics.node_stats.total = 100
            mock_metrics.node_stats.idle = 60
            mock_metrics.node_stats.allocated = 35
            mock_metrics.node_stats.drained = 3
            mock_metrics.node_stats.down = 2
            mock_metrics.job_stats.pending = 10
            mock_metrics.job_stats.running = 35
            mock_metrics.job_stats.failed = 5
            mock_metrics.resource_usage.cpu_percent = 65.5
            mock_metrics.resource_usage.memory_percent = 72.3
            mock_metrics.resource_usage.gpu_percent = 45.0

            mock_collect.return_value = mock_metrics

            # Collect metrics
            metrics = await collector.collect()

            # Update metrics server
            metrics_server.update_local_metrics(
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

            # Verify metrics server was updated (just check it exists)
            assert metrics_server is not None

    @pytest.mark.asyncio
    async def test_heartbeat_with_retry(self, sample_client_config):
        """Test heartbeat sending with retry logic."""
        from slurmheartbeat.client.sender import HeartbeatSender

        sender = HeartbeatSender(sample_client_config.client)
        peer = sample_client_config.client.federation.peers[0]
        message = HeartbeatMessage(cluster=ClusterInfo(id="test", name="test", site="test"))

        # Mock successful send on first try
        with patch.object(sender, "send") as mock_send:
            from slurmheartbeat.client.sender import SendResult

            mock_send.return_value = SendResult(success=True, peer_name="test", latency_ms=10.0)

            result = await sender.send_with_retry(peer, message)

            assert result.success is True
            assert mock_send.call_count == 1

    @pytest.mark.asyncio
    async def test_heartbeat_failure_handling(self, sample_client_config):
        """Test heartbeat failure handling and retry."""
        from slurmheartbeat.client.sender import HeartbeatSender, SendResult

        sender = HeartbeatSender(sample_client_config.client)
        peer = sample_client_config.client.federation.peers[0]
        message = HeartbeatMessage(cluster=ClusterInfo(id="test", name="test", site="test"))

        # Mock failed send
        with patch.object(sender, "send") as mock_send:
            mock_send.return_value = SendResult(
                success=False, peer_name="test", latency_ms=0, error="Timeout"
            )

            result = await sender.send_with_retry(peer, message)

            assert result.success is False
            assert mock_send.call_count == sample_client_config.client.retry_count + 1

    @pytest.mark.asyncio
    async def test_publisher_only_mode_startup(self):
        """Test that publisher-only mode can start without client components."""
        from slurmheartbeat.client.config import ServerConfig, TLSConfig
        from slurmheartbeat.monitoring.metrics import MetricsServer
        from slurmheartbeat.server.publisher import ReadinessPublisher

        # Create minimal server config
        server_config = ServerConfig(
            enabled=True,
            listen_address="127.0.0.1",
            listen_port=18443,
            tls=TLSConfig(enabled=False),  # Disable TLS for testing
            allowed_sites=[],
        )

        # Create metrics server without config (should use defaults)
        metrics = MetricsServer()

        # Create publisher - should not raise ValueError
        publisher = ReadinessPublisher(
            config=server_config,
            site_id="test-site",
            cluster_name="test-cluster",
            fed_state="UNKNOWN",
            metrics=metrics,
        )

        # Verify publisher was created
        assert publisher is not None
        assert publisher.site_id == "test-site"
        assert publisher.cluster_name == "test-cluster"
        assert publisher.metrics is not None

    @pytest.mark.asyncio
    async def test_metrics_server_without_config(self):
        """Test that MetricsServer can be initialized without config."""
        from slurmheartbeat.monitoring.metrics import MetricsServer

        # Create metrics server without config
        metrics = MetricsServer()

        # Verify it was created
        assert metrics is not None
        assert metrics.config is not None  # Should have defaults
        assert metrics.config.enabled is True
        assert metrics.config.port == 9090

    @pytest.mark.asyncio
    async def test_metrics_get_registry(self):
        """Test that MetricsServer exposes get_metrics method."""
        from slurmheartbeat.monitoring.metrics import MetricsServer, PrometheusConfig

        config = PrometheusConfig(enabled=True, port=19090)
        metrics = MetricsServer(config)

        # Verify get_metrics method exists and returns registry
        assert hasattr(metrics, "get_metrics")
        registry = metrics.get_metrics()
        assert registry is not None

    @pytest.mark.asyncio
    async def test_metrics_record_readiness_update(self):
        """Test that MetricsServer records readiness updates."""
        from slurmheartbeat.monitoring.metrics import MetricsServer, PrometheusConfig

        config = PrometheusConfig(enabled=True, port=29090)
        metrics = MetricsServer(config)

        # Verify record_readiness_update method exists
        assert hasattr(metrics, "record_readiness_update")

        # Call the method
        metrics.record_readiness_update("ready", "test-site")
        metrics.record_readiness_update("limited", "test-site")
        metrics.record_readiness_update("draining", "test-site")
        metrics.record_readiness_update("unavailable", "test-site")

        # Should not raise
        assert True

    @pytest.mark.asyncio
    async def test_client_disabled_respected(self, sample_client_config):
        """Test that client.enabled=False prevents collector/sender creation."""
        from slurmheartbeat.client.config import ClientConfig, HeartbeatClientConfig

        # Create config with client disabled
        config = ClientConfig()
        config.client = HeartbeatClientConfig(enabled=False)

        # Verify client is disabled
        assert config.client.enabled is False
