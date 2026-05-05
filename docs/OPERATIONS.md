# Slurm Heartbeat - Operations Guide

This guide provides operational procedures for running the Slurm Heartbeat daemon in production.

## Daily Operations

### Checking Service Status

```bash
# Check if service is running
sudo systemctl status slurm-heartbeat

# View recent logs
sudo journalctl -u slurm-heartbeat -n 50

# Check for errors
sudo journalctl -u slurm-heartbeat -p err -n 100
```

### Monitoring Metrics

```bash
# View Prometheus metrics
curl http://localhost:9090/metrics | grep slurmheartbeat

# Check peer status
curl http://localhost:9090/metrics | grep federation_member_status

# Check heartbeat latency
curl http://localhost:9090/metrics | grep heartbeat_latency
```

### Checking Federation Health

```bash
# View readiness endpoint (requires mTLS client cert)
curl --cert cert.pem --key key.pem --cacert ca.pem https://localhost:8443/readiness

# View metrics
curl http://localhost:9090/metrics | grep slurmheartbeat
```

**Note**: The legacy `FederationState.load()` method and state file persistence are not implemented. Peer state is tracked in-memory only and rebuilt from heartbeats on restart.

## Weekly Operations

### Review Logs

```bash
# Check for recurring errors
sudo journalctl -u slurm-heartbeat --since "1 week ago" | grep -i error | head -20

# Check for certificate warnings
sudo journalctl -u slurm-heartbeat --since "1 week ago" | grep -i cert
```

### Verify Certificates

```bash
# Check certificate expiration
openssl x509 -in /etc/slurm/heartbeat/cert.pem -noout -dates

# Verify certificate chain
openssl verify -CAfile /etc/slurm/heartbeat/ca.pem /etc/slurm/heartbeat/cert.pem
```

### Review Alerts

- Check alerting dashboard for any unresolved alerts
- Review alert history for patterns
- Update alerting thresholds if needed

## Monthly Operations

### Performance Review

```bash
# Check memory usage
ps -o pid,rss,command -p $(cat /var/run/slurm/heartbeat.pid)

# Check CPU usage (last 30 days)
sudo systemctl status slurm-heartbeat --no-pager | grep -i cpu

# Review latency metrics
curl http://localhost:9090/metrics | grep heartbeat_latency_seconds
```

### Configuration Audit

```bash
# Compare current config with baseline
diff /etc/slurm/heartbeat/config.yaml /path/to/baseline/config.yaml

# Validate configuration syntax
python -c "import yaml; yaml.safe_load(open('/etc/slurm/heartbeat/config.yaml'))"
```

### Update Documentation

- Update federation peer list if changes occurred
- Document any configuration changes
- Review and update runbooks

## Troubleshooting

### Service Won't Start

**Symptoms**: `systemctl status slurm-heartbeat` shows failed state

**Steps**:
1. Check error logs:
   ```bash
   sudo journalctl -u slurm-heartbeat -n 100
   ```
2. Verify configuration:
   ```bash
   python -c "from slurmheartbeat.client.config import Config; Config.load('/etc/slurm/heartbeat/config.yaml')"
   ```
3. Check certificate files:
   ```bash
   ls -la /etc/slurm/heartbeat/
   ```
4. Verify Slurm API connectivity:
   ```bash
   curl http://localhost:6820/slurm/v0.0.39/ping
   ```

### High Latency

**Symptoms**: `heartbeat_latency_seconds` > 5s

**Steps**:
1. Check network connectivity to peers:
   ```bash
   ping <peer-hostname>
   traceroute <peer-hostname>
   ```
2. Check firewall rules:
   ```bash
   sudo iptables -L -n | grep 8443
   ```
3. Review peer load:
   ```bash
   curl http://<peer-hostname>:9090/metrics | grep process_cpu
   ```
4. Consider increasing timeout:
   ```yaml
   client:
     timeout_seconds: 60
   ```

### Peer Marked as Down

**Symptoms**: `federation_member_status{site="X"} == 0`

**Steps**:
1. Check if peer is reachable:
   ```bash
   curl -k https://<peer-hostname>:8443/heartbeat
   ```
2. Check peer logs:
   ```bash
   ssh <peer-hostname> "sudo journalctl -u slurm-heartbeat -n 50"
   ```
3. Verify certificate validity:
   ```bash
   openssl s_client -connect <peer-hostname>:8443 -showcerts
   ```
4. Check for network partitions:
   ```bash
   mtr <peer-hostname>
   ```

### Certificate Expiry

**Symptoms**: Logs show "certificate expiring soon" or "certificate expired"

**Steps**:
1. Check expiry date:
   ```bash
   openssl x509 -in /etc/slurm/heartbeat/cert.pem -noout -enddate
   ```
2. Generate new certificate:
   ```bash
   ./scripts/generate_certs.sh
   ```
3. Deploy new certificate:
   ```bash
   sudo cp certs/server.pem /etc/slurm/heartbeat/cert.pem
   sudo cp certs/server.key /etc/slurm/heartbeat/key.pem
   sudo systemctl reload slurm-heartbeat
   ```

## Disaster Recovery

### Complete Service Failure

**Scenario**: Daemon crashed and won't start

**Recovery Steps**:
1. Check system resources:
   ```bash
   free -h
   df -h
   ```
2. Review recent changes:
   ```bash
   git log --oneline -10
   ```
3. Restore from backup:
   ```bash
   sudo cp /backup/heartbeat/config.yaml /etc/slurm/heartbeat/config.yaml
   sudo cp /backup/heartbeat/certs/* /etc/slurm/heartbeat/
   ```
4. Restart service:
   ```bash
   sudo systemctl start slurm-heartbeat
   ```
5. Verify operation:
   ```bash
   sudo systemctl status slurm-heartbeat
   ```

### Federation Partition

**Scenario**: Network partition between federation members

**Recovery Steps**:
1. Identify partition:
   ```bash
   for peer in lumi-prod leapi-italy jaeger-germany; do
     echo -n "$peer: "
     curl -k -s -o /dev/null -w "%{http_code}" https://$peer:8443/heartbeat || echo "unreachable"
   done
   ```
2. Check network infrastructure:
   - Contact network team
   - Check firewall rules
   - Verify routing tables
3. Monitor for reconnection:
   ```bash
   watch -n 5 'curl http://localhost:9090/metrics | grep federation_member_status'
   ```
4. Once reconnected, verify state sync:
   ```bash
   sudo journalctl -u slurm-heartbeat | grep "state sync"
   ```

### Data Corruption

**Scenario**: State file corrupted

**Recovery Steps**:
1. Stop service:
   ```bash
   sudo systemctl stop slurm-heartbeat
   ```
2. Backup corrupted state:
   ```bash
   sudo cp /var/lib/slurm/heartbeat/state.json /var/lib/slurm/heartbeat/state.json.corrupted
   ```
3. Remove corrupted state:
   ```bash
   sudo rm /var/lib/slurm/heartbeat/state.json
   ```
4. Restart service (will rebuild state):
   ```bash
   sudo systemctl start slurm-heartbeat
   ```
5. Monitor state rebuild:
   ```bash
   sudo journalctl -u slurm-heartbeat | grep "state"
   ```

## Maintenance Windows

### Scheduled Maintenance

**Before maintenance**:
1. Notify federation members
2. Document current state
3. Take configuration backup

**During maintenance**:
1. Stop service:
   ```bash
   sudo systemctl stop slurm-heartbeat
   ```
2. Perform maintenance tasks
3. Verify changes

**After maintenance**:
1. Start service:
   ```bash
   sudo systemctl start slurm-heartbeat
   ```
2. Verify operation:
   ```bash
   sudo systemctl status slurm-heartbeat
   ```
3. Check federation connectivity:
   ```bash
   watch -n 5 'curl http://localhost:9090/metrics | grep federation_member_status'
   ```

### Certificate Rotation

**Schedule**: 30 days before expiry

**Steps**:
1. Generate new certificate:
   ```bash
   ./scripts/generate_certs.sh
   ```
2. Deploy to staging:
   ```bash
   sudo cp certs/server.pem /etc/slurm/heartbeat/staging_cert.pem
   sudo cp certs/server.key /etc/slurm/heartbeat/staging_key.pem
   ```
3. Test with staging config
4. Deploy to production:
   ```bash
   sudo cp /etc/slurm/heartbeat/staging_cert.pem /etc/slurm/heartbeat/cert.pem
   sudo cp /etc/slurm/heartbeat/staging_key.pem /etc/slurm/heartbeat/key.pem
   sudo systemctl reload slurm-heartbeat
   ```
5. Verify:
   ```bash
   sudo systemctl status slurm-heartbeat
   ```

## Escalation Procedures

### Level 1 (On-Call)

- Service not running
- Single peer down
- High latency (>5s)
- Certificate expiring (<30 days)

**Actions**:
- Follow runbook
- Check logs and metrics
- Restart service if needed
- Escalate if unresolved in 30 minutes

### Level 2 (Site Admin)

- Multiple peers down
- Service won't start
- Certificate issues
- Configuration problems

**Actions**:
- Investigate root cause
- Coordinate with affected sites
- Implement fixes
- Escalate to Level 3 if needed

### Level 3 (EFP Operations)

- Federation-wide issues
- Security incidents
- Major outages
- Cross-site coordination needed

**Actions**:
- Coordinate across sites
- Engage EFP operations team
- Implement federation-wide fixes
- Post-incident review

## Contact Information

| Role | Contact | Escalation Time |
|------|---------|-----------------|
| On-Call | ops-oncall@example.com | Immediate |
| Site Admin | site-admin@example.com | 30 minutes |
| EFP Operations | efp-ops@example.com | 1 hour |
| Security | security@example.com | Immediate (security issues) |

## Runbook Checklist

### Daily

- [ ] Check service status
- [ ] Review error logs
- [ ] Verify peer connectivity
- [ ] Check alerting dashboard

### Weekly

- [ ] Review weekly logs
- [ ] Verify certificate validity
- [ ] Check performance metrics
- [ ] Review alert history

### Monthly

- [ ] Performance review
- [ ] Configuration audit
- [ ] Update documentation
- [ ] Security review

### As Needed

- [ ] Certificate rotation
- [ ] Configuration changes
- [ ] Incident response
- [ ] Disaster recovery
