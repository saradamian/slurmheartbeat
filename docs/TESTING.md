# Slurm Heartbeat - Testing Guide

This document outlines testing strategies and procedures for the Slurm Heartbeat daemon.

## Test Types

### Unit Tests

Unit tests verify individual components in isolation:

- **Protocol Tests**: Message serialization/deserialization, signing
- **Client Tests**: Heartbeat sender, retry logic
- **Server Tests**: Heartbeat receiver, peer state management
- **Metrics Tests**: Prometheus metric collection

Run unit tests:
```bash
pytest tests/test_protocol.py tests/test_client.py tests/test_server.py -v
```

### Integration Tests

Integration tests verify component interactions:

- **Client-Server Communication**: End-to-end heartbeat flow
- **TLS Handshake**: Certificate validation, mutual authentication
- **Slurm API Integration**: Metrics collection from Slurm REST API

Run integration tests:
```bash
pytest tests/test_integration.py -v --integration
```

### Performance Tests

Performance tests measure overhead and scalability:

- **Latency**: Time to send/receive heartbeat
- **Throughput**: Maximum heartbeats per second
- **Memory**: Memory usage under load

Run performance tests:
```bash
pytest tests/test_performance.py -v --performance
```

## Test Setup

### Prerequisites

- Python 3.10+
- pytest and pytest-asyncio
- httpx for async HTTP testing
- Slurm REST API (optional, for integration tests)

### Test Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install test dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov pytest-mock
```

## Running Tests

### All Tests

```bash
./scripts/run_tests.sh
```

### With Coverage

```bash
./scripts/run_tests.sh --coverage
```

### Specific Test File

```bash
pytest tests/test_protocol.py -v
```

### Specific Test Function

```bash
pytest tests/test_protocol.py::test_heartbeat_message_serialization -v
```

## Test Coverage Goals

| Module | Target Coverage |
|--------|----------------|
| `protocol/message.py` | 90% |
| `client/sender.py` | 85% |
| `server/receiver.py` | 85% |
| `monitoring/metrics.py` | 80% |
| `protocol/security.py` | 75% |
| **Overall** | **85%** |

## Test Examples

### Protocol Test Example

```python
import pytest
from slurmheartbeat.protocol.message import HeartbeatMessage, ClusterInfo

def test_heartbeat_message_serialization():
    """Test message serialization and deserialization."""
    message = HeartbeatMessage(
        cluster=ClusterInfo(id="test", name="test-cluster", site="test-site"),
        status="healthy",
    )
    
    # Serialize
    json_str = message.to_json()
    
    # Deserialize
    restored = HeartbeatMessage.from_dict(message.to_dict())
    
    assert restored.cluster.id == message.cluster.id
    assert restored.status == message.status
```

### Client Test Example

```python
import pytest
from unittest.mock import AsyncMock, patch
from slurmheartbeat.client.sender import HeartbeatSender

@pytest.mark.asyncio
async def test_heartbeat_sender_sends_message():
    """Test that sender successfully sends heartbeat."""
    config = ClientConfig()
    sender = HeartbeatSender(config)
    
    peer = PeerConfig(name="test", endpoint="http://localhost:8443", site="test")
    message = HeartbeatMessage()
    
    with patch('httpx.AsyncClient.post') as mock_post:
        mock_post.return_value = AsyncMock(status_code=200)
        
        result = await sender.send(peer, message)
        
        assert result.success
        assert result.peer_name == "test"
```

### Server Test Example

```python
import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from slurmheartbeat.server.receiver import HeartbeatReceiver

class TestHeartbeatReceiver(AioHTTPTestCase):
    async def get_application(self):
        config = ServerConfig()
        receiver = HeartbeatReceiver(config)
        
        app = web.Application()
        app.router.add_post("/heartbeat", receiver._handle_heartbeat)
        return app
    
    @unittest_run_loop
    async def test_heartbeat_endpoint(self):
        """Test heartbeat endpoint accepts valid messages."""
        data = {"cluster": {"id": "test", "name": "test", "site": "test"}}
        
        async with self.client.post("/heartbeat", json=data) as resp:
            assert resp.status == 200
```

## Continuous Integration

### GitHub Actions Workflow

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python: [3.10, 3.11, 3.12]
    
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python }}
      - name: Install dependencies
        run: |
          python -m venv venv
          source venv/bin/activate
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov
      - name: Run tests
        run: ./scripts/run_tests.sh --coverage
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Manual Testing

### Test Heartbeat Flow

1. **Start server**:
   ```bash
   python -m slurmheartbeat.server --config config.test.yaml
   ```

2. **Start client** (in another terminal):
   ```bash
   python -m slurmheartbeat.client --config config.test.yaml
   ```

3. **Check logs**:
   ```bash
   tail -f /var/log/slurm/heartbeat.log
   ```

4. **Verify metrics**:
   ```bash
   curl http://localhost:9090/metrics
   ```

### Test TLS Handshake

```bash
# Test server certificate
openssl s_client -connect localhost:8443 -CAfile /etc/slurm/heartbeat/ca.pem

# Test client certificate
openssl s_client -connect localhost:8443 -cert /etc/slurm/heartbeat/cert.pem \
    -key /etc/slurm/heartbeat/key.pem -CAfile /etc/slurm/heartbeat/ca.pem
```

## Troubleshooting

### Common Test Failures

| Issue | Solution |
|-------|----------|
| `ImportError` | Ensure virtual environment is activated |
| `Connection refused` | Verify Slurm REST API is running |
| `TLS handshake failed` | Check certificate paths and permissions |
| `Async test timeout` | Increase pytest timeout: `pytest --timeout=60` |

### Debug Mode

Run tests with verbose output:
```bash
pytest -v -s --tb=long
```

Run tests with logging:
```bash
pytest -v --log-cli-level=DEBUG
```

## Performance Benchmarking

### Latency Test

```python
import time
import asyncio
from slurmheartbeat.client.sender import HeartbeatSender

async def benchmark_latency():
    sender = HeartbeatSender(config)
    peer = PeerConfig(name="test", endpoint="http://localhost:8443", site="test")
    message = HeartbeatMessage()
    
    latencies = []
    for _ in range(100):
        start = time.time()
        await sender.send(peer, message)
        latencies.append(time.time() - start)
    
    print(f"Average latency: {sum(latencies)/len(latencies)*1000:.2f}ms")
    print(f"P99 latency: {sorted(latencies)[99]*1000:.2f}ms")
```

## Security Testing

### Certificate Validation

```bash
# Test with expired certificate
openssl x509 -in cert.pem -checkend 0 && echo "Valid" || echo "Expired"

# Test certificate chain
openssl verify -CAfile ca.pem cert.pem
```

### Penetration Testing

Use tools like:
- **nmap**: Scan for open ports
- **sslscan**: Test TLS configuration
- **burp suite**: Test API endpoints

```bash
# Scan heartbeat port
nmap -sV -p 8443 localhost

# Test TLS configuration
sslscan localhost:8443
```

---

**END OF TESTING GUIDE**
