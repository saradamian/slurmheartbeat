"""Tests for Slurm Heartbeat metrics."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from slurmheartbeat.monitoring.metrics import MetricsServer, PrometheusConfig


class TestMetricsServer:
    """Tests for MetricsServer class."""

    def setup_method(self):
        """Reset singleton state before each test."""
        MetricsServer._instance = None
        MetricsServer._metrics_initialized = False

    def teardown_method(self):
        """Reset singleton state after each test."""
        MetricsServer._instance = None
        MetricsServer._metrics_initialized = False

    def test_create_metrics_server(self):
        """Test creating metrics server."""
        config = PrometheusConfig()
        server = MetricsServer(config)

        assert server.config == config
        assert server._running is False

    @pytest.mark.asyncio
    async def test_start_disabled(self):
        """Test starting disabled metrics server."""
        config = PrometheusConfig(enabled=False)
        server = MetricsServer(config)

        await server.start()

        assert server._running is False

    @pytest.mark.asyncio
    async def test_start_enabled(self):
        """Test starting enabled metrics server."""
        config = PrometheusConfig(enabled=True, port=9090)
        server = MetricsServer(config)

        with patch("slurmheartbeat.monitoring.metrics.start_http_server") as mock_start:
            await server.start()

            assert server._running is True
            mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop(self):
        """Test stopping metrics server."""
        config = PrometheusConfig(enabled=True)
        server = MetricsServer(config)
        server._running = True

        await server.stop()

        assert server._running is False

    def test_record_heartbeat_sent(self):
        """Test recording heartbeat sent."""
        config = PrometheusConfig()
        server = MetricsServer(config)

        with patch.object(server.heartbeat_sent, "labels") as mock_labels:
            mock_counter = MagicMock()
            mock_labels.return_value = mock_counter

            server.record_heartbeat_sent("test-site")

            mock_labels.assert_called_once_with(site="test-site")
            mock_counter.inc.assert_called_once()

    def test_record_heartbeat_received(self):
        """Test recording heartbeat received."""
        config = PrometheusConfig()
        server = MetricsServer(config)

        with patch.object(server.heartbeat_received, "labels") as mock_labels:
            mock_counter = MagicMock()
            mock_labels.return_value = mock_counter

            server.record_heartbeat_received("test-site")

            mock_labels.assert_called_once_with(site="test-site")
            mock_counter.inc.assert_called_once()

    def test_record_heartbeat_error(self):
        """Test recording heartbeat error."""
        config = PrometheusConfig()
        server = MetricsServer(config)

        with patch.object(server.heartbeat_errors, "labels") as mock_labels:
            mock_counter = MagicMock()
            mock_labels.return_value = mock_counter

            server.record_heartbeat_error("test-site", "timeout")

            mock_labels.assert_called_once_with(site="test-site", error_type="timeout")
            mock_counter.inc.assert_called_once()

    def test_record_heartbeat_latency(self):
        """Test recording heartbeat latency."""
        config = PrometheusConfig()
        server = MetricsServer(config)

        with patch.object(server.heartbeat_latency, "labels") as mock_labels:
            mock_histogram = MagicMock()
            mock_labels.return_value = mock_histogram

            server.record_heartbeat_latency("test-site", 0.05)

            mock_labels.assert_called_once_with(site="test-site")
            mock_histogram.observe.assert_called_once_with(0.05)

    def test_update_peer_status(self):
        """Test updating peer status."""
        config = PrometheusConfig()
        server = MetricsServer(config)

        with (
            patch.object(server.peer_status, "labels") as mock_status_labels,
            patch.object(server.peer_last_seen, "labels") as mock_seen_labels,
            patch.object(server.peer_consecutive_failures, "labels") as mock_failures_labels,
        ):
            mock_gauge = MagicMock()
            mock_status_labels.return_value = mock_gauge
            mock_seen_labels.return_value = mock_gauge
            mock_failures_labels.return_value = mock_gauge

            server.update_peer_status("test-site", "healthy", 10.0, 0)

            mock_status_labels.assert_called_once_with(site="test-site")
            mock_seen_labels.assert_called_once_with(site="test-site")
            mock_failures_labels.assert_called_once_with(site="test-site")
            assert mock_gauge.set.call_count == 3

    def test_update_local_metrics(self):
        """Test updating local metrics."""
        config = PrometheusConfig()
        server = MetricsServer(config)

        with (
            patch.object(server.local_node_total, "set") as mock_total,
            patch.object(server.local_node_idle, "set") as mock_idle,
            patch.object(server.local_node_allocated, "set") as mock_allocated,
            patch.object(server.local_node_drained, "set") as mock_drained,
            patch.object(server.local_node_down, "set") as mock_down,
            patch.object(server.local_jobs_pending, "set") as mock_pending,
            patch.object(server.local_jobs_running, "set") as mock_running,
            patch.object(server.local_jobs_failed, "set") as mock_failed,
            patch.object(server.local_cpu_percent, "set") as mock_cpu,
            patch.object(server.local_memory_percent, "set") as mock_memory,
            patch.object(server.local_gpu_percent, "set") as mock_gpu,
        ):
            server.update_local_metrics(
                node_total=100,
                node_idle=60,
                node_allocated=35,
                node_drained=3,
                node_down=2,
                jobs_pending=10,
                jobs_running=35,
                jobs_failed=5,
                cpu_percent=65.5,
                memory_percent=72.3,
                gpu_percent=45.0,
            )

            mock_total.assert_called_once_with(100)
            mock_idle.assert_called_once_with(60)
            mock_allocated.assert_called_once_with(35)
            mock_drained.assert_called_once_with(3)
            mock_down.assert_called_once_with(2)
            mock_pending.assert_called_once_with(10)
            mock_running.assert_called_once_with(35)
            mock_failed.assert_called_once_with(5)
            mock_cpu.assert_called_once_with(65.5)
            mock_memory.assert_called_once_with(72.3)
            mock_gpu.assert_called_once_with(45.0)

    def test_get_metrics_returns_string(self):
        """Test that get_metrics returns a string (Prometheus text format)."""
        config = PrometheusConfig()
        server = MetricsServer(config)

        result = server.get_metrics()

        assert isinstance(result, str)
        assert "slurmheartbeat_" in result  # Should contain our metrics

    def test_record_readiness_update_with_site(self):
        """Test recording readiness update with site parameter."""
        config = PrometheusConfig()
        server = MetricsServer(config)

        with patch.object(server.peer_status, "labels") as mock_labels:
            mock_gauge = MagicMock()
            mock_labels.return_value = mock_gauge

            server.record_readiness_update("ready", "test-site")

            mock_labels.assert_called_once_with(site="test-site")
            mock_gauge.set.assert_called_once_with(1)  # ready = 1

    def test_record_readiness_update_all_statuses(self):
        """Test recording readiness update for all status values."""
        config = PrometheusConfig()
        server = MetricsServer(config)

        status_map = {
            "ready": 1,
            "limited": 0,
            "draining": -1,
            "unavailable": -2,
            "unknown": 0,
        }

        for status, expected_value in status_map.items():
            with patch.object(server.peer_status, "labels") as mock_labels:
                mock_gauge = MagicMock()
                mock_labels.return_value = mock_gauge

                server.record_readiness_update(status, "test-site")

                mock_labels.assert_called_with(site="test-site")
                mock_gauge.set.assert_called_with(expected_value)
