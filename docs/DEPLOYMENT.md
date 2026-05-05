# Slurm Heartbeat - Deployment Guide

This guide covers deployment of the Slurm Heartbeat daemon to production environments.

## Prerequisites

- Python 3.10+
- Slurm 21.08+ with REST API enabled
- OpenSSL 1.1.1+ for TLS 1.3
- Systemd (for service management)
- Root/sudo access for installation

## Installation Steps

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv /opt/slurm-heartbeat/venv
source /opt/slurm-heartbeat/venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Generate Certificates

```bash
# Generate TLS certificates
./scripts/generate_certs.sh your-site-name /etc/slurm/heartbeat

# Verify certificates
openssl x509 -in /etc/slurm/heartbeat/cert.pem -text -noout
```

### 3. Configure Daemon

```bash
# Copy example configuration
cp config.example.yaml /etc/slurm/heartbeat/config.yaml

# Edit configuration
vim /etc/slurm/heartbeat/config.yaml
```

**Key configuration settings:**

```yaml
general:
  log_level: "INFO"
  log_file: "/var/log/slurm/heartbeat.log"

client:
  interval_seconds: 10
  slurm:
    api_url: "http://localhost:6820"
    api_version: "0.0.39"

server:
  listen_port: 8443
  tls:
    enabled: true
    cert_file: "/etc/slurm/heartbeat/cert.pem"
    key_file: "/etc/slurm/heartbeat/key.pem"
    ca_file: "/etc/slurm/heartbeat/ca.pem"
    client_auth: "required"

federation:
  peers:
    - name: "lumi-prod"
      endpoint: "https://lumi.example.com:8443/heartbeat"
      site: "CSC Finland"
```

### 4. Install Systemd Service

```bash
# Install service file
sudo cp systemd/slurm-heartbeat.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable slurm-heartbeat

# Start service
sudo systemctl start slurm-heartbeat

# Check status
sudo systemctl status slurm-heartbeat
```

### 5. Verify Deployment

```bash
# Check logs
sudo journalctl -u slurm-heartbeat -f

# Check metrics
curl http://localhost:9090/metrics

# Check health endpoint
curl -k https://localhost:8443/health

# Check readiness endpoint (requires mTLS client cert)
curl --cert cert.pem --key key.pem --cacert ca.pem https://localhost:8443/readiness
```

## Production Checklist

### Pre-Deployment

- [ ] TLS certificates generated and valid
- [ ] Configuration file reviewed and updated
- [ ] Firewall rules configured (port 8443, 9090)
- [ ] Slurm REST API accessible
- [ ] Peer endpoints verified
- [ ] Log directory exists and writable
- [ ] Service file installed

### Post-Deployment

- [ ] Service running (`systemctl status`)
- [ ] Logs accessible (`journalctl -u`)
- [ ] Metrics endpoint responding
- [ ] Heartbeat sent to peers
- [ ] Heartbeat received from peers
- [ ] Alerting configured and tested

## Monitoring

### Systemd Monitoring

```bash
# Check service status
sudo systemctl status slurm-heartbeat

# View recent logs
sudo journalctl -u slurm-heartbeat -n 50

# Follow logs
sudo journalctl -u slurm-heartbeat -f
```

### Prometheus Monitoring

Configure Prometheus to scrape metrics:

```yaml
scrape_configs:
  - job_name: 'slurm-heartbeat'
    static_configs:
      - targets: ['localhost:9090']
    metrics_path: /metrics
    scheme: http
```

### Alerting Rules

```yaml
groups:
  - name: slurm-heartbeat
    rules:
      - alert: HeartbeatServiceDown
        expr: up{job="slurm-heartbeat"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Slurm heartbeat service is down"

      - alert: HeartbeatPeerDown
        expr: slurmheartbeat_member_status == -1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Federation peer {{ $labels.site }} is down"

      - alert: HeartbeatHighLatency
        expr: histogram_quantile(0.99, slurmheartbeat_latency_seconds_bucket) > 1
        labels:
          severity: warning
        annotations:
          summary: "Heartbeat latency is high (P99 > 1s)"
```

## Troubleshooting

### Service Won't Start

```bash
# Check service status
sudo systemctl status slurm-heartbeat

# Check logs
sudo journalctl -u slurm-heartbeat -n 100

# Check configuration
python -m slurmheartbeat --config /etc/slurm/heartbeat/config.yaml --dry-run

# Check permissions
ls -la /etc/slurm/heartbeat/
ls -la /var/log/slurm/
```

### TLS Errors

```bash
# Verify certificate chain
openssl verify -CAfile /etc/slurm/heartbeat/ca.pem /etc/slurm/heartbeat/cert.pem

# Check certificate expiry
openssl x509 -in /etc/slurm/heartbeat/cert.pem -noout -dates

# Test TLS connection
openssl s_client -connect localhost:8443 -CAfile /etc/slurm/heartbeat/ca.pem
```

### Peer Connection Issues

```bash
# Test peer endpoint
curl -k https://peer.example.com:8443/health

# Check firewall
sudo iptables -L -n | grep 8443

# Check network connectivity
ping peer.example.com
traceroute peer.example.com
```

### High Latency

```bash
# Check system load
top -b -n 1 | head -20

# Check network latency
ping -c 10 peer.example.com

# Check metrics
curl http://localhost:9090/metrics | grep latency
```

## Certificate Rotation

### Manual Rotation

```bash
# Generate new certificate
./scripts/generate_certs.sh your-site-name /etc/slurm/heartbeat

# Backup old certificate
sudo cp /etc/slurm/heartbeat/cert.pem /etc/slurm/heartbeat/cert.pem.backup

# Deploy new certificate
sudo cp /etc/slurm/heartbeat/site.pem /etc/slurm/heartbeat/cert.pem
sudo cp /etc/slurm/heartbeat/site.key /etc/slurm/heartbeat/key.pem

# Restart service
sudo systemctl restart slurm-heartbeat

# Verify
sudo systemctl status slurm-heartbeat
```

### Automated Rotation (Recommended)

Use a certificate management tool like `certbot` or custom script:

```bash
#!/bin/bash
# /usr/local/bin/rotate-cert.sh

CERT_DIR="/etc/slurm/heartbeat"
BACKUP_DIR="/var/backups/slurm-heartbeat"

# Generate new certificate
./scripts/generate_certs.sh "$(hostname)" "$CERT_DIR"

# Backup old certificate
cp "$CERT_DIR/cert.pem" "$BACKUP_DIR/cert.$(date +%Y%m%d).pem"
cp "$CERT_DIR/key.pem" "$BACKUP_DIR/key.$(date +%Y%m%d).pem"

# Restart service
systemctl restart slurm-heartbeat

# Log rotation
logger "Slurm heartbeat certificate rotated"
```

Add to crontab:
```cron
0 2 1 * 0 /usr/local/bin/rotate-cert.sh
```

## Scaling

### Multiple Instances

For high availability, run multiple instances:

```bash
# Instance 1
sudo cp systemd/slurm-heartbeat.service /etc/systemd/system/slurm-heartbeat-1.service
# Edit: change listen_port to 8443, log_file to heartbeat-1.log

# Instance 2
sudo cp systemd/slurm-heartbeat.service /etc/systemd/system/slurm-heartbeat-2.service
# Edit: change listen_port to 8444, log_file to heartbeat-2.log

sudo systemctl daemon-reload
sudo systemctl enable slurm-heartbeat-1 slurm-heartbeat-2
sudo systemctl start slurm-heartbeat-1 slurm-heartbeat-2
```

### Load Balancing

Use a load balancer (HAProxy, nginx) for multiple instances:

```nginx
upstream heartbeat_servers {
    server 10.0.1.10:8443;
    server 10.0.1.11:8443;
    server 10.0.1.12:8443;
}

server {
    listen 8443 ssl;
    ssl_certificate /etc/ssl/certs/heartbeat.pem;
    ssl_certificate_key /etc/ssl/private/heartbeat.key;

    location /heartbeat {
        proxy_pass https://heartbeat_servers;
        proxy_ssl_verify off;
    }
}
```

## Upgrades

### Rolling Upgrade

```bash
# Stop service
sudo systemctl stop slurm-heartbeat

# Backup configuration
sudo cp /etc/slurm/heartbeat/config.yaml /etc/slurm/heartbeat/config.yaml.backup

# Update code
cd /opt/slurm-heartbeat
git pull
source venv/bin/activate
pip install -r requirements.txt

# Restart service
sudo systemctl start slurm-heartbeat

# Verify
sudo systemctl status slurm-heartbeat
```

### Rollback

```bash
# Stop service
sudo systemctl stop slurm-heartbeat

# Restore configuration
sudo cp /etc/slurm/heartbeat/config.yaml.backup /etc/slurm/heartbeat/config.yaml

# Restore previous version
cd /opt/slurm-heartbeat
git checkout HEAD~1
pip install -r requirements.txt

# Restart service
sudo systemctl start slurm-heartbeat
```

## Security Hardening

### File Permissions

```bash
# Restrict certificate access
sudo chmod 600 /etc/slurm/heartbeat/key.pem
sudo chmod 644 /etc/slurm/heartbeat/cert.pem
sudo chmod 644 /etc/slurm/heartbeat/ca.pem

# Restrict configuration
sudo chmod 600 /etc/slurm/heartbeat/config.yaml

# Restrict log files
sudo chmod 640 /var/log/slurm/heartbeat.log
```

### Network Security

```bash
# Firewall rules (UFW)
sudo ufw allow from 10.0.0.0/8 to any port 8443 proto tcp
sudo ufw allow from 10.0.0.0/8 to any port 9090 proto tcp
sudo ufw deny 8443
sudo ufw deny 9090

# Firewall rules (iptables)
sudo iptables -A INPUT -p tcp -s 10.0.0.0/8 --dport 8443 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8443 -j DROP
```

### Service Hardening

```ini
# In systemd service file
[Service]
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/var/log/slurm /var/run/slurm
```

## References

- [Slurm REST API Documentation](https://slurm.schedmd.com/rest_api.html)
- [TLS 1.3 RFC](https://datatracker.ietf.org/doc/html/rfc8446)
- [Systemd Service Documentation](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [Prometheus Metrics Guide](https://prometheus.io/docs/instrumenting/writing_exporters/)

---

**END OF DEPLOYMENT GUIDE**
