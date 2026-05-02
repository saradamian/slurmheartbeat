"""Tests for Slurm Heartbeat client sender."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from slurmheartbeat.client.config import HeartbeatClientConfig, PeerConfig
from slurmheartbeat.client.sender import HeartbeatSender, SendResult
from slurmheartbeat.protocol.message import ClusterInfo, HeartbeatMessage


class TestHeartbeatSender:
    """Tests for HeartbeatSender class."""

    def test_create_sender(self):
        """Test creating heartbeat sender."""
        config = HeartbeatClientConfig()
        sender = HeartbeatSender(config)

        assert sender.config == config
        assert sender._client is None

    @pytest.mark.asyncio
    async def test_send_success(self):
        """Test successful heartbeat send."""
        config = HeartbeatClientConfig()
        sender = HeartbeatSender(config)

        peer = PeerConfig(name="test", endpoint="http://localhost:8443", site="test")
        message = HeartbeatMessage(cluster=ClusterInfo(id="test", name="test", site="test"))

        with patch.object(sender, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await sender.send(peer, message)

            assert result.success is True
            assert result.peer_name == "test"
            assert result.error is None

    @pytest.mark.asyncio
    async def test_send_timeout(self):
        """Test heartbeat send timeout."""
        config = HeartbeatClientConfig()
        sender = HeartbeatSender(config)

        peer = PeerConfig(name="test", endpoint="http://localhost:8443", site="test")
        message = HeartbeatMessage(cluster=ClusterInfo(id="test", name="test", site="test"))

        with patch.object(sender, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Timeout")
            mock_get_client.return_value = mock_client

            result = await sender.send(peer, message)

            assert result.success is False
            assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_send_connection_error(self):
        """Test heartbeat send connection error."""
        config = HeartbeatClientConfig()
        sender = HeartbeatSender(config)

        peer = PeerConfig(name="test", endpoint="http://localhost:8443", site="test")
        message = HeartbeatMessage(cluster=ClusterInfo(id="test", name="test", site="test"))

        with patch.object(sender, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Connection refused")
            mock_get_client.return_value = mock_client

            result = await sender.send(peer, message)

            assert result.success is False
            assert "Connection" in result.error

    @pytest.mark.asyncio
    async def test_send_with_retry_success(self):
        """Test heartbeat send with retry succeeds on first try."""
        config = HeartbeatClientConfig(retry_count=3)
        sender = HeartbeatSender(config)

        peer = PeerConfig(name="test", endpoint="http://localhost:8443", site="test")
        message = HeartbeatMessage(cluster=ClusterInfo(id="test", name="test", site="test"))

        with patch.object(sender, "send") as mock_send:
            mock_send.return_value = SendResult(success=True, peer_name="test", latency_ms=10.0)

            result = await sender.send_with_retry(peer, message)

            assert result.success is True
            assert mock_send.call_count == 1

    @pytest.mark.asyncio
    async def test_send_with_retry_failure(self):
        """Test heartbeat send with retry fails after all attempts."""
        config = HeartbeatClientConfig(retry_count=2, retry_backoff=0.1)
        sender = HeartbeatSender(config)

        peer = PeerConfig(name="test", endpoint="http://localhost:8443", site="test")
        message = HeartbeatMessage(cluster=ClusterInfo(id="test", name="test", site="test"))

        with patch.object(sender, "send") as mock_send:
            mock_send.return_value = SendResult(
                success=False, peer_name="test", latency_ms=0, error="Error"
            )

            result = await sender.send_with_retry(peer, message)

            assert result.success is False
            assert mock_send.call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_send_to_all(self):
        """Test sending heartbeat to all peers."""
        config = HeartbeatClientConfig()
        config.federation.peers = [
            PeerConfig(name="peer1", endpoint="http://localhost:8443", site="test"),
            PeerConfig(name="peer2", endpoint="http://localhost:8444", site="test"),
        ]
        sender = HeartbeatSender(config)

        message = HeartbeatMessage(cluster=ClusterInfo(id="test", name="test", site="test"))

        with patch.object(sender, "send_with_retry") as mock_send:
            mock_send.return_value = SendResult(success=True, peer_name="test", latency_ms=10.0)

            results = await sender.send_to_all(message)

            assert len(results) == 2
            assert all(r.success for r in results)
            assert mock_send.call_count == 2

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing sender."""
        config = HeartbeatClientConfig()
        sender = HeartbeatSender(config)

        mock_client = AsyncMock()
        mock_client.is_closed = False
        sender._client = mock_client

        await sender.close()

        mock_client.aclose.assert_called_once()
