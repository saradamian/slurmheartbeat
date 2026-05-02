# Slurm Heartbeat - Security Guide

This document outlines security considerations and best practices for deploying the Slurm Heartbeat daemon.

## Threat Model

### Assets to Protect

1. **Federation Health Data**: Cluster status, resource availability
2. **Authentication Credentials**: TLS certificates, private keys
3. **Communication Channels**: Heartbeat messages between sites
4. **System Integrity**: Daemon process, configuration files

### Threat Actors

- **External attackers**: Attempting to disrupt federation
- **Malicious insiders**: Compromised site administrators
- **Network attackers**: Man-in-the-middle on federation links

### Attack Vectors

- **Certificate forgery**: Impersonating federation members
- **Message injection**: Sending fake heartbeat data
- **Denial of service**: Overwhelming heartbeat endpoints
- **Replay attacks**: Capturing and replaying valid heartbeats

## Security Controls

### 1. Transport Security

#### TLS 1.3

All heartbeat communication must use TLS 1.3:

```yaml
server:
  tls:
    enabled: true
    min_version: "1.3"
    max_version: "1.3"
    cert_file: "/etc/slurm/heartbeat/cert.pem"
    key_file: "/etc/slurm/heartbeat/key.pem"
    ca_file: "/etc/slurm/heartbeat/ca.pem"
    client_auth: "required"
```

#### Certificate Requirements

- **Key size**: Minimum 4096-bit RSA or 256-bit ECC
- **Validity**: Maximum 1 year (annual rotation)
- **Subject**: CN=site-name, O=federation, C=EU
- **Extensions**: Extended Key Usage for clientAuth and serverAuth

### 2. Authentication

#### Mutual TLS (mTLS)

Both client and server present certificates:

1. Client presents certificate to server
2. Server validates client certificate against CA
3. Server presents certificate to client
4. Client validates server certificate against CA

#### Certificate Validation

```python
def validate_certificate(cert: x509.Certificate) -> bool:
    """Validate certificate for federation membership."""
    # Check expiration
    if cert.not_valid_after < datetime.now():
        return False
    
    # Check subject
    subject = cert.subject
    if "O" not in subject or subject.get_attributes(NameOID.ORGANIZATION)[0].value != "EFP":
        return False
    
    # Check extensions
    try:
        ext_key_usage = cert.extensions.get_extension_for_class(ExtendedKeyUsage)
        if not (ext_key_usage.value.client_auth or ext_key_usage.value.server_auth):
            return False
    except ExtensionNotFound:
        return False
    
    return True
```

### 3. Authorization

#### Access Control Lists

Restrict which federation members can communicate:

```yaml
federation:
  allowed_sites:
    - "csc-finland"
    - "cineca-italy"
    - "hlrs-germany"
  blocked_sites: []
```

#### Certificate-Based Authorization

Map certificate CN/OU to allowed sites:

```python
def authorize_peer(cert: x509.Certificate, allowed_sites: list) -> bool:
    """Authorize peer based on certificate subject."""
    cn = cert.subject.get_attributes(NameOID.COMMON_NAME)[0].value
    return cn in allowed_sites
```

### 4. Message Integrity

#### Signature Verification

Optionally sign heartbeat messages:

```python
import hashlib
import hmac

def sign_message(message: dict, private_key: str) -> str:
    """Sign heartbeat message with private key."""
    message_json = json.dumps(message, sort_keys=True)
    signature = hmac.new(
        private_key.encode(),
        message_json.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature

def verify_message(message: dict, signature: str, public_key: str) -> bool:
    """Verify heartbeat message signature."""
    expected = sign_message(message, public_key)
    return hmac.compare_digest(expected, signature)
```

### 5. Rate Limiting

Prevent denial of service:

```yaml
security:
  rate_limit:
    enabled: true
    requests_per_minute: 60
    burst_size: 10
```

### 6. Network Security

#### Firewall Rules

```bash
# Allow heartbeat port from federation members only
iptables -A INPUT -p tcp -s 10.0.1.0/24 --dport 8443 -j ACCEPT
iptables -A INPUT -p tcp -s 10.0.2.0/24 --dport 8443 -j ACCEPT
iptables -A INPUT -p tcp --dport 8443 -j DROP

# Restrict metrics endpoint to internal network
iptables -A INPUT -p tcp -s 10.0.0.0/8 --dport 9090 -j ACCEPT
iptables -A INPUT -p tcp --dport 9090 -j DROP
```

#### Network Segmentation

- Place heartbeat service on dedicated management network
- Use VLANs to isolate federation traffic
- Implement network monitoring for anomalies

## Certificate Management

### Generation

```bash
# Generate CA key and certificate
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -key ca.key \
    -sha256 -days 365 -out ca.pem \
    -subj "/CN=EFP CA/O=EFP/C=EU"

# Generate site certificate
openssl genrsa -out site.key 4096
openssl req -new -key site.key -out site.csr \
    -subj "/CN=site-name/O=EFP/C=EU"

# Sign site certificate
openssl x509 -req -in site.csr \
    -CA ca.pem -CAkey ca.key -CAcreateserial \
    -out site.pem -days 365 -sha256 \
    -extfile site.ext
```

### Rotation

**Annual rotation schedule:**

1. **90 days before expiry**: Generate new certificate
2. **60 days before**: Deploy new certificate to staging
3. **30 days before**: Deploy to production
4. **On expiry**: Revoke old certificate

**Rotation script:**

```bash
#!/bin/bash
# rotate_cert.sh

CERT_DIR="/etc/slurm/heartbeat"
CA_DIR="/etc/slurm/heartbeat-ca"

# Generate new certificate
./scripts/generate_site_cert.sh "$SITE_NAME" > "$CERT_DIR/new.pem"

# Backup old certificate
cp "$CERT_DIR/server.pem" "$CERT_DIR/server.pem.backup"

# Deploy new certificate
cp "$CERT_DIR/new.pem" "$CERT_DIR/server.pem"

# Restart service
systemctl reload slurm-heartbeat

# Verify
systemctl status slurm-heartbeat
```

## Security Monitoring

### Logging

Enable detailed security logging:

```yaml
general:
  log_level: "INFO"
  log_format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### Security Events to Monitor

| Event | Severity | Action |
|-------|----------|--------|
| Invalid certificate | CRITICAL | Block peer, alert |
| Failed authentication | HIGH | Log, monitor pattern |
| Rate limit exceeded | MEDIUM | Log, consider blocking |
| Certificate expiring soon | LOW | Alert admin |
| Unusual traffic pattern | MEDIUM | Investigate |

### Alerting Rules

```yaml
alerting:
  rules:
    - name: InvalidCertificate
      condition: "authentication_failed AND cert_invalid"
      severity: critical
      action: "block_peer, alert_ops"
      
    - name: RateLimitExceeded
      condition: "requests_per_minute > 100"
      severity: warning
      action: "log, monitor"
```

## Compliance Considerations

### GDPR

- **Data minimization**: Only collect necessary metrics
- **Data sovereignty**: Ensure cross-border data transfers comply
- **Audit logging**: Maintain logs for compliance review

### Security Standards

- **NIST SP 800-53**: Access control, audit and accountability
- **ISO 27001**: Information security management
- **CIS Controls**: Network security, encryption

## Incident Response

### Detected Breach

1. **Isolate**: Block compromised site from federation
2. **Assess**: Determine scope of compromise
3. **Revoke**: Revoke compromised certificates
4. **Notify**: Inform EFP security team
5. **Restore**: Deploy new certificates
6. **Review**: Post-incident analysis

### Certificate Compromise

1. **Revoke**: Add to CRL/OCSP
2. **Notify**: Inform all federation members
3. **Rotate**: Generate new certificates
4. **Audit**: Check for unauthorized access

## Security Checklist

### Pre-Deployment

- [ ] TLS 1.3 enabled
- [ ] Certificates generated with strong keys
- [ ] Certificate validation implemented
- [ ] Access control lists configured
- [ ] Rate limiting enabled
- [ ] Firewall rules in place
- [ ] Logging configured
- [ ] Security testing completed

### Post-Deployment

- [ ] Service running with minimal privileges
- [ ] Certificates stored securely (chmod 600)
- [ ] Metrics endpoint restricted
- [ ] Regular security audits scheduled
- [ ] Incident response plan documented
- [ ] Certificate rotation schedule established

## References

- [TLS 1.3 RFC](https://datatracker.ietf.org/doc/html/rfc8446)
- [NIST SP 800-52r2](https://csrc.nist.gov/publications/detail/sp/800-52/rev-2/final)
- [CIS Controls v8](https://www.cisecurity.org/controls)
- [GDPR](https://gdpr.eu/)
