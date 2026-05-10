"""Tests for federation discovery component."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from slurmheartbeat.client.config import FederationConfig, PeerConfig
from slurmheartbeat.federation.discovery import FederationDiscovery, FederationPeer, FederationState
from slurmheartbeat.protocol.schema import CapacityHint


class TestFederationPeer:
    """Test FederationPeer class."""

    def test_peer_is_healthy_recent(self):
        """Test peer is healthy when recently seen."""
        peer = FederationPeer(
            name="test-peer",
            endpoint="https://test.example.com/readiness",
            site="Test Site",
            last_seen=datetime.utcnow(),
            consecutive_failures=0,
        )
        assert peer.is_healthy() is True

    def test_peer_is_healthy_old(self):
        """Test peer is unhealthy when not seen recently."""
        peer = FederationPeer(
            name="test-peer",
            endpoint="https://test.example.com/readiness",
            site="Test Site",
            last_seen=datetime.utcnow() - timedelta(seconds=200),
            consecutive_failures=0,
        )
        assert peer.is_healthy(max_age_seconds=120) is False

    def test_peer_is_healthy_failures(self):
        """Test peer is unhealthy after too many failures."""
        peer = FederationPeer(
            name="test-peer",
            endpoint="https://test.example.com/readiness",
            site="Test Site",
            last_seen=datetime.utcnow(),
            consecutive_failures=3,
        )
        assert peer.is_healthy() is False


class TestFederationState:
    """Test FederationState class."""

    def test_get_healthy_peers(self):
        """Test getting healthy peers."""
        state = FederationState()
        state.peers["peer1"] = FederationPeer(
            name="peer1",
            endpoint="https://peer1.example.com/readiness",
            site="Site 1",
            last_seen=datetime.utcnow(),
            consecutive_failures=0,
        )
        state.peers["peer2"] = FederationPeer(
            name="peer2",
            endpoint="https://peer2.example.com/readiness",
            site="Site 2",
            last_seen=datetime.utcnow() - timedelta(seconds=200),
            consecutive_failures=0,
        )

        healthy = state.get_healthy_peers()
        assert len(healthy) == 1
        assert healthy[0].name == "peer1"

    def test_get_total_capacity(self):
        """Test aggregating capacity across peers."""
        state = FederationState()
        state.peers["peer1"] = FederationPeer(
            name="peer1",
            endpoint="https://peer1.example.com/readiness",
            site="Site 1",
            capacity_hint=CapacityHint(idle_nodes=10, pending_jobs=5),
            last_seen=datetime.utcnow(),
        )
        state.peers["peer2"] = FederationPeer(
            name="peer2",
            endpoint="https://peer2.example.com/readiness",
            site="Site 2",
            capacity_hint=CapacityHint(idle_nodes=20, pending_jobs=10),
            last_seen=datetime.utcnow(),
        )

        total = state.get_total_capacity()
        assert total.idle_nodes == 30
        assert total.pending_jobs == 15


class TestFederationDiscovery:
    """Test FederationDiscovery class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = MagicMock()
        config.client.federation = FederationConfig(
            peers=[
                PeerConfig(name="peer1", endpoint="https://peer1.example.com", site="Site 1"),
                PeerConfig(name="peer2", endpoint="https://peer2.example.com", site="Site 2"),
            ]
        )
        return config

    @pytest.mark.asyncio
    async def test_discover_peers(self, mock_config):
        """Test peer discovery from config."""
        discovery = FederationDiscovery(mock_config)
        peers = await discovery.discover_peers()

        assert len(peers) == 2
        assert peers[0].name == "peer1"
        assert peers[1].name == "peer2"
        assert len(discovery.state.peers) == 2

    @pytest.mark.asyncio
    async def test_fetch_peer_capacity_success(self, mock_config):
        """Test fetching capacity from peer on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "site_id": "peer1",
            "status": "ready",
            "capacity_hint": {"idle_nodes": 10, "pending_jobs": 5},
            "signals": {"queue_pressure": "low"},
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        discovery = FederationDiscovery(mock_config, http_client=mock_client)
        await discovery.discover_peers()

        peer = discovery.state.peers["peer1"]
        capacity = await discovery.fetch_peer_capacity(peer, timeout=5)

        assert capacity is not None
        assert capacity.idle_nodes == 10
        assert capacity.pending_jobs == 5
        assert peer.last_seen is not None
        assert peer.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_fetch_peer_capacity_timeout(self, mock_config):
        """Test fetching capacity from peer on timeout."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")

        discovery = FederationDiscovery(mock_config, http_client=mock_client)
        await discovery.discover_peers()

        peer = discovery.state.peers["peer1"]
        capacity = await discovery.fetch_peer_capacity(peer, timeout=5)

        assert capacity is None
        assert peer.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_fetch_all_peers(self, mock_config):
        """Test fetching from all peers in parallel."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "site_id": "peer1",
            "status": "ready",
            "capacity_hint": {"idle_nodes": 10, "pending_jobs": 5},
            "signals": {"queue_pressure": "low"},
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        discovery = FederationDiscovery(mock_config, http_client=mock_client)
        await discovery.discover_peers()

        results = await discovery.fetch_all_peers(timeout=5)

        assert "peer1" in results
        assert "peer2" in results
        assert results["peer1"] is not None
