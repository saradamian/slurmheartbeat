"""Tests for Slurm Heartbeat server receiver."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from slurmheartbeat.client.config import ServerConfig
from slurmheartbeat.protocol.message import ClusterInfo, HeartbeatMessage
from slurmheartbeat.server.publisher import ReadinessPublisher
from slurmheartbeat.server.receiver import FederationState, HeartbeatReceiver


class TestFederationState:
    """Tests for FederationState class."""

    @pytest.mark.asyncio
    async def test_update_peer(self):
        """Test updating peer state."""
        config = ServerConfig()
        state = FederationState(config)

        message = HeartbeatMessage(
            cluster=ClusterInfo(id="test", name="test", site="test"),
            status="healthy",
        )

        peer = await state.update_peer("test-peer", message, 10.0)

        assert peer.name == "test-peer"
        assert peer.status == "healthy"
        assert peer.consecutive_failures == 0
        assert peer.last_latency_ms == 10.0

    @pytest.mark.asyncio
    async def test_record_failure(self):
        """Test recording peer failure."""
        config = ServerConfig()
        state = FederationState(config)

        peer = await state.record_failure("test-peer", "Connection error")

        assert peer.name == "test-peer"
        assert peer.consecutive_failures == 1
        assert peer.error == "Connection error"

    @pytest.mark.asyncio
    async def test_get_peer(self):
        """Test getting peer state."""
        config = ServerConfig()
        state = FederationState(config)

        message = HeartbeatMessage(
            cluster=ClusterInfo(id="test", name="test", site="test"),
            status="healthy",
        )

        await state.update_peer("test-peer", message, 10.0)
        peer = await state.get_peer("test-peer")

        assert peer is not None
        assert peer.name == "test-peer"

    @pytest.mark.asyncio
    async def test_get_peer_not_found(self):
        """Test getting non-existent peer."""
        config = ServerConfig()
        state = FederationState(config)

        peer = await state.get_peer("non-existent")

        assert peer is None

    @pytest.mark.asyncio
    async def test_get_all_peers(self):
        """Test getting all peers."""
        config = ServerConfig()
        state = FederationState(config)

        message = HeartbeatMessage(
            cluster=ClusterInfo(id="test", name="test", site="test"),
            status="healthy",
        )

        await state.update_peer("peer1", message, 10.0)
        await state.update_peer("peer2", message, 15.0)

        peers = await state.get_all_peers()

        assert len(peers) == 2
        assert {p.name for p in peers} == {"peer1", "peer2"}

    @pytest.mark.asyncio
    async def test_get_healthy_peers(self):
        """Test getting healthy peers."""
        config = ServerConfig()
        state = FederationState(config)

        healthy_message = HeartbeatMessage(
            cluster=ClusterInfo(id="test", name="test", site="test"),
            status="healthy",
        )
        unhealthy_message = HeartbeatMessage(
            cluster=ClusterInfo(id="test", name="test", site="test"),
            status="unhealthy",
        )

        await state.update_peer("healthy-peer", healthy_message, 10.0)
        await state.update_peer("unhealthy-peer", unhealthy_message, 10.0)

        healthy_peers = await state.get_healthy_peers()

        assert len(healthy_peers) == 1
        assert healthy_peers[0].name == "healthy-peer"


class TestHeartbeatReceiver:
    """Tests for HeartbeatReceiver class."""

    def test_create_receiver(self):
        """Test creating heartbeat receiver."""
        config = ServerConfig()
        receiver = HeartbeatReceiver(config)

        assert receiver.config == config
        assert receiver.state is not None

    @pytest.mark.asyncio
    async def test_handle_heartbeat_success(self, sample_heartbeat_message):
        """Test handling successful heartbeat."""
        config = ServerConfig()
        receiver = HeartbeatReceiver(config)

        # Set allowed members for authorization
        receiver.state.set_allowed_members(["test-cluster"])

        # Mock request with client certificate
        mock_request = AsyncMock()
        mock_request.json.return_value = sample_heartbeat_message.to_dict()
        mock_request.query = {}
        mock_request.remote = "127.0.0.1"

        # Mock transport with client certificate
        mock_transport = AsyncMock()

        def get_extra_info(key):
            if key == "peercert":
                # Format: tuple of tuples where each inner tuple is (oid, value)
                return {
                    "subject": (("commonName", "test-cluster"),),
                    "issuer": (("commonName", "EFP CA"),),
                }
            elif key == "ssl_object":
                # Fallback for ssl_object
                ssl_obj = AsyncMock()
                ssl_obj.getpeercert.return_value = {
                    "subject": (("commonName", "test-cluster"),),
                    "issuer": (("commonName", "EFP CA"),),
                }
                return ssl_obj
            return None

        mock_transport.get_extra_info = get_extra_info
        mock_request.transport = mock_transport

        response = await receiver._handle_heartbeat(mock_request)

        assert response.status == 200

    @pytest.mark.asyncio
    async def test_handle_heartbeat_invalid_json(self):
        """Test handling invalid JSON."""
        config = ServerConfig()
        receiver = HeartbeatReceiver(config)

        mock_request = AsyncMock()
        mock_request.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)

        response = await receiver._handle_heartbeat(mock_request)

        assert response.status == 400

    @pytest.mark.asyncio
    async def test_handle_heartbeat_invalid_message(self):
        """Test handling invalid message."""
        config = ServerConfig()
        receiver = HeartbeatReceiver(config)

        # Set allowed members for authorization
        receiver.state.set_allowed_members(["test-cluster"])

        mock_request = AsyncMock()
        mock_request.json.return_value = {"invalid": "data"}
        mock_request.query = {}
        mock_request.remote = "127.0.0.1"

        # Mock transport with client certificate
        mock_transport = AsyncMock()

        def get_extra_info(key):
            if key == "peercert":
                return {
                    "subject": (("commonName", "test-cluster"),),
                    "issuer": (("commonName", "EFP CA"),),
                }
            elif key == "ssl_object":
                ssl_obj = AsyncMock()
                ssl_obj.getpeercert.return_value = {
                    "subject": (("commonName", "test-cluster"),),
                    "issuer": (("commonName", "EFP CA"),),
                }
                return ssl_obj
            return None

        mock_transport.get_extra_info = get_extra_info
        mock_request.transport = mock_transport

        response = await receiver._handle_heartbeat(mock_request)

        # Should still succeed as from_dict handles missing fields
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_handle_health(self):
        """Test health check endpoint."""
        config = ServerConfig()
        receiver = HeartbeatReceiver(config)

        mock_request = AsyncMock()
        response = await receiver._handle_health(mock_request)

        assert response.status == 200

    @pytest.mark.asyncio
    async def test_handle_peers(self):
        """Test peers endpoint."""
        config = ServerConfig()
        receiver = HeartbeatReceiver(config)

        message = HeartbeatMessage(
            cluster=ClusterInfo(id="test", name="test", site="test"),
            status="healthy",
        )

        await receiver.state.update_peer("test-peer", message, 10.0)

        mock_request = AsyncMock()
        response = await receiver._handle_peers(mock_request)

        assert response.status == 200

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        """Test starting and stopping receiver."""
        config = ServerConfig()
        config.listen_port = 18443  # Use non-privileged port for testing
        config.tls.enabled = False  # Disable TLS for testing
        receiver = HeartbeatReceiver(config)

        # Start should not raise
        await receiver.start()
        assert receiver._running is True

        # Stop should not raise
        await receiver.stop()
        assert receiver._running is False

    @pytest.mark.asyncio
    async def test_get_state(self):
        """Test getting receiver state."""
        config = ServerConfig()
        receiver = HeartbeatReceiver(config)

        message = HeartbeatMessage(
            cluster=ClusterInfo(id="test", name="test", site="test"),
            status="healthy",
        )

        await receiver.state.update_peer("test-peer", message, 10.0)

        state = await receiver.get_state()

        assert "peers" in state
        assert len(state["peers"]) == 1
        assert state["peers"][0]["name"] == "test-peer"

    def test_set_peer_public_key(self):
        """Test setting peer public key."""
        config = ServerConfig()
        state = FederationState(config)

        public_key = "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----"
        state.set_peer_public_key("test-peer", public_key)

        assert state.get_peer_public_key("test-peer") == public_key

    def test_get_peer_public_key_not_found(self):
        """Test getting non-existent peer public key."""
        config = ServerConfig()
        state = FederationState(config)

        assert state.get_peer_public_key("non-existent") is None

    @pytest.mark.asyncio
    async def test_handle_heartbeat_with_signature_verification(self, sample_heartbeat_message):
        """Test heartbeat with signature verification."""
        config = ServerConfig()
        receiver = HeartbeatReceiver(config)

        # Set allowed members and public key
        receiver.state.set_allowed_members(["test-cluster"])
        public_key = "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----"
        receiver.state.set_peer_public_key("test-cluster", public_key)

        # Mock request with client certificate
        mock_request = AsyncMock()
        mock_request.json.return_value = sample_heartbeat_message.to_dict()
        mock_request.query = {}
        mock_request.remote = "127.0.0.1"

        # Mock transport with client certificate
        mock_transport = AsyncMock()

        def get_extra_info(key):
            if key == "peercert":
                return {
                    "subject": (("commonName", "test-cluster"),),
                    "issuer": (("commonName", "EFP CA"),),
                }
            elif key == "ssl_object":
                ssl_obj = AsyncMock()
                ssl_obj.getpeercert.return_value = {
                    "subject": (("commonName", "test-cluster"),),
                    "issuer": (("commonName", "EFP CA"),),
                }
                return ssl_obj
            return None

        mock_transport.get_extra_info = get_extra_info
        mock_request.transport = mock_transport

        # Mock signature verification to return True
        with patch.object(HeartbeatMessage, "verify_signature", return_value=True):
            response = await receiver._handle_heartbeat(mock_request)

        assert response.status == 200

    @pytest.mark.asyncio
    async def test_handle_heartbeat_missing_public_key(self, sample_heartbeat_message):
        """Test heartbeat fails when public key not configured but signature is present."""
        config = ServerConfig()
        receiver = HeartbeatReceiver(config)

        # Set allowed members but NO public key
        receiver.state.set_allowed_members(["test-cluster"])

        # Create a message WITH a signature
        message_with_sig = sample_heartbeat_message
        message_with_sig.signature = "deadbeef"  # Add a fake signature

        # Mock request with client certificate
        mock_request = AsyncMock()
        mock_request.json.return_value = message_with_sig.to_dict()
        mock_request.query = {}
        mock_request.remote = "127.0.0.1"

        # Mock transport with client certificate
        mock_transport = AsyncMock()

        def get_extra_info(key):
            if key == "peercert":
                return {
                    "subject": (("commonName", "test-cluster"),),
                    "issuer": (("commonName", "EFP CA"),),
                }
            elif key == "ssl_object":
                ssl_obj = AsyncMock()
                ssl_obj.getpeercert.return_value = {
                    "subject": (("commonName", "test-cluster"),),
                    "issuer": (("commonName", "EFP CA"),),
                }
                return ssl_obj
            return None

        mock_transport.get_extra_info = get_extra_info
        mock_request.transport = mock_transport

        # Should fail because no public key is configured but signature is present
        response = await receiver._handle_heartbeat(mock_request)

        assert response.status == 403


class TestReadinessPublisher:
    """Tests for ReadinessPublisher class."""

    def test_create_publisher(self):
        """Test creating readiness publisher."""
        config = ServerConfig()
        publisher = ReadinessPublisher(config, "test-site", "test-cluster")

        assert publisher.site_id == "test-site"
        assert publisher.cluster_name == "test-cluster"
        assert publisher.state.site_id == "test-site"
        assert publisher.state.cluster_name == "test-cluster"

    def test_update_readiness(self):
        """Test updating readiness state."""
        config = ServerConfig()
        publisher = ReadinessPublisher(config, "test-site", "test-cluster")

        # Create a readiness message
        from slurmheartbeat.protocol.schema import (
            CapacityHint,
            ReadinessMessage,
            ReadinessStatus,
            Signals,
        )

        readiness = ReadinessMessage(
            site_id="test-site",
            cluster_name="test-cluster",
            status=ReadinessStatus.READY,
            signals=Signals(),
            capacity_hint=CapacityHint(),
        )

        # Update readiness
        publisher.update_readiness(readiness)

        assert publisher.state.last_readiness == readiness
        assert publisher.state.last_update is not None

    @pytest.mark.asyncio
    async def test_handle_metrics_returns_string(self):
        """Test that /metrics handler returns string, not awaits registry."""
        from slurmheartbeat.client.config import PrometheusConfig

        config = ServerConfig()
        prometheus_config = PrometheusConfig(enabled=True)
        publisher = ReadinessPublisher(config, "test-site", "test-cluster", prometheus_config=prometheus_config)

        # Get metrics - should return string, not awaitable
        metrics_text = publisher._metrics.get_metrics()

        assert isinstance(metrics_text, str)
        assert "slurmheartbeat_" in metrics_text
