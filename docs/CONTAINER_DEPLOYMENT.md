# Containerized Deployment Guide

This guide covers running Slurm Heartbeat in Docker containers.

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- OpenSSL 1.1.1+ (for certificate generation)

## Quick Start

### 1. Generate Certificates

```bash
# Create certificates directory
mkdir -p certs

# Generate self-signed certificates (for testing)
./scripts/generate_certs.sh test ./certs

# For production, use your site's CA or EFP CA
```

### 2. Configure

```bash
# Copy example configuration
cp config.example.yaml config.yaml

# Edit configuration
vim config.yaml

# Key settings for Docker:
# - server.listen_port: 8443 (matches container port)
# - monitoring.port: 9090 (matches container port)
# - tls.cert_file: /etc/slurm/heartbeat/server.crt
# - tls.key_file: /etc/slurm/heartbeat/server.key
```

### 3. Run with Docker Compose

```bash
# Start all services (heartbeat + Prometheus)
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f slurm-heartbeat

# View Prometheus metrics
open http://localhost:9091
```

### 4. Verify

```bash
# Check health endpoint
curl -k https://localhost:8443/health

# Check readiness (requires client cert)
curl --cert certs/client.crt --key certs/client.key --cacert certs/ca.crt \
    https://localhost:8443/readiness

# Check Prometheus metrics
curl http://localhost:9090/metrics
```

## Standalone Docker (Without Compose)

```bash
# Build image
docker build -t slurm-heartbeat .

# Run container
docker run -d \
  --name slurm-heartbeat \
  -p 8443:8443 \
  -p 9090:9090 \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/certs:/etc/slurm/heartbeat:ro \
  -v heartbeat-logs:/var/log/slurm-heartbeat \
  slurm-heartbeat
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SLURM_HEARTBEAT_CONFIG` | Path to config file | `/app/config.yaml` |
| `SLURM_HEARTBEAT_MODE` | Operation mode | `both` |
| `SLURM_HEARTBEAT_VERBOSE` | Enable verbose logging | `false` |

### Volume Mounts

| Path | Purpose | Required |
|------|---------|----------|
| `/app/config.yaml` | Configuration file | Yes |
| `/etc/slurm/heartbeat/` | TLS certificates | Yes |
| `/var/log/slurm-heartbeat/` | Log files | No |

## Production Deployment

### Security Hardening

```bash
# Run as non-root user (already in Dockerfile)
# Use read-only filesystem where possible
# Enable seccomp profiles
# Use Docker secrets for sensitive data
```

### Resource Limits

```yaml
# In docker-compose.yml
services:
  slurm-heartbeat:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
        reservations:
          cpus: '0.1'
          memory: 64M
```

### Health Checks

```bash
# Built-in health check (every 30s)
docker inspect --format='{{.State.Health.Status}}' slurm-heartbeat

# Manual health check
curl -k https://localhost:8443/health
```

### Logging

```bash
# View container logs
docker-compose logs -f slurm-heartbeat

# View last 100 lines
docker-compose logs --tail=100 slurm-heartbeat

# Save logs to file
docker-compose logs slurm-heartbeat > heartbeat.log
```

## Updating

```bash
# Pull latest image
docker-compose pull

# Restart services
docker-compose up -d

# Verify update
docker-compose ps
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs slurm-heartbeat

# Check configuration
docker-compose run --rm slurm-heartbeat python -m slurmheartbeat --config /app/config.yaml --dry-run

# Verify certificate paths
docker-compose run --rm slurm-heartbeat ls -la /etc/slurm/heartbeat/
```

### Health Check Fails

```bash
# Check if service is running
docker-compose exec slurm-heartbeat curl -k https://localhost:8443/health

# Check certificate validity
docker-compose exec slurm-heartbeat openssl x509 -in /etc/slurm/heartbeat/server.crt -noout -dates
```

### Metrics Not Scraping

```bash
# Check Prometheus config
docker-compose exec prometheus cat /etc/prometheus/prometheus.yml

# Check target status
open http://localhost:9091/targets
```

## Development

### Build Local Image

```bash
docker build -t slurm-heartbeat:dev .
```

### Run with Hot Reload

```bash
# Mount source code for development
docker run -d \
  --name slurm-heartbeat-dev \
  -p 8443:8443 \
  -p 9090:9090 \
  -v $(pwd):/app \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  slurm-heartbeat:dev
```

### Run Tests in Container

```bash
docker-compose run --rm slurm-heartbeat pytest tests/ -v
```

## References

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [Slurm Heartbeat Installation](INSTALLATION.md)
- [Slurm Heartbeat Deployment](DEPLOYMENT.md)

---

**END OF CONTAINERIZED DEPLOYMENT GUIDE**
