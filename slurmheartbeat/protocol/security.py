"""TLS and certificate handling for heartbeat communication."""

from __future__ import annotations

import logging
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

logger = logging.getLogger(__name__)


@dataclass
class TLSConfig:
    """TLS configuration for heartbeat communication."""

    enabled: bool = True
    cert_file: str = "/etc/slurm/heartbeat/cert.pem"
    key_file: str = "/etc/slurm/heartbeat/key.pem"
    ca_file: str = "/etc/slurm/heartbeat/ca.pem"
    client_auth: str = "required"  # "required", "optional", "disabled"
    min_version: str = "1.3"
    max_version: str = "1.3"


def create_ssl_context(
    cert_file: str,
    key_file: str,
    ca_file: str | None = None,
    client_auth: str = "required",
    min_version: str = "1.3",
    max_version: str = "1.3",
) -> ssl.SSLContext:
    """Create SSL context for heartbeat communication.

    Args:
        cert_file: Path to certificate file.
        key_file: Path to private key file.
        ca_file: Path to CA certificate file (optional for client auth).
        client_auth: Client authentication mode.
        min_version: Minimum TLS version.
        max_version: Maximum TLS version.

    Returns:
        Configured SSL context.
    """
    # Create context with TLS 1.3
    if min_version == "1.3":
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.maximum_version = ssl.TLSVersion.TLSv1_3
    else:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2

    # Load certificate and key
    context.load_cert_chain(
        certfile=cert_file,
        keyfile=key_file,
    )

    # Configure client authentication
    if client_auth == "required":
        context.verify_mode = ssl.CERT_REQUIRED
        if ca_file:
            context.load_verify_locations(ca_file)
    elif client_auth == "optional":
        context.verify_mode = ssl.CERT_OPTIONAL
        if ca_file:
            context.load_verify_locations(ca_file)
    else:
        context.verify_mode = ssl.CERT_NONE

    # Set secure defaults
    context.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20")
    context.options |= ssl.OP_NO_SSLv2
    context.options |= ssl.OP_NO_SSLv3
    context.options |= ssl.OP_NO_TLSv1
    context.options |= ssl.OP_NO_TLSv1_1

    logger.info(
        f"SSL context created with TLS {min_version}-{max_version}, client_auth={client_auth}"
    )

    return context


def create_client_ssl_context(
    cert_file: str,
    key_file: str,
    ca_file: str,
    verify: bool = True,
) -> ssl.SSLContext:
    """Create SSL context for client connections.

    Args:
        cert_file: Path to client certificate file.
        key_file: Path to client key file.
        ca_file: Path to CA certificate file.
        verify: Whether to verify server certificates.

    Returns:
        Configured SSL context.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3

    # Load client certificate and key
    context.load_cert_chain(
        certfile=cert_file,
        keyfile=key_file,
    )

    # Configure server verification
    if verify:
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(ca_file)
    else:
        context.verify_mode = ssl.CERT_NONE

    # Set secure defaults
    context.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20")

    logger.info(f"Client SSL context created with TLS 1.3, verify={verify}")

    return context


def generate_ca_certificate(
    common_name: str = "EFP Heartbeat CA",
    organization: str = "EFP",
    country: str = "EU",
    validity_days: int = 3650,  # 10 years
    key_size: int = 4096,
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    """Generate a CA certificate and private key.

    Args:
        common_name: Common name for the certificate.
        organization: Organization name.
        country: Country code.
        validity_days: Certificate validity in days.
        key_size: RSA key size in bits.

    Returns:
        Tuple of (certificate, private key).
    """
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )

    # Build certificate
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )

    import datetime

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=validity_days))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                key_cert_sign=True,
                key_agreement=False,
                content_commitment=False,
                data_encipherment=False,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(private_key, hashes.SHA256())
    )

    return cert, private_key


def load_private_key(key_file: str, password: str | None = None) -> Any:
    """Load a private key from a file.

    Args:
        key_file: Path to private key file.
        password: Optional password for encrypted key.

    Returns:
        Loaded private key (Any type to support different key types).
    """
    from pathlib import Path

    key_path = Path(key_file)
    if not key_path.exists():
        raise FileNotFoundError(f"Private key file not found: {key_file}")

    with open(key_path, "rb") as f:
        key_data = f.read()

    # Try loading with password first if provided
    if password:
        try:
            return serialization.load_pem_private_key(
                key_data,
                password=password.encode(),
            )
        except Exception:
            logger.debug(f"Failed to load key with password from {key_file}")
            pass

    # Try loading without password
    return serialization.load_pem_private_key(
        key_data,
        password=None,
    )


def generate_site_certificate(
    ca_cert: x509.Certificate,
    ca_key: rsa.RSAPrivateKey,
    common_name: str,
    organization: str,
    country: str = "EU",
    validity_days: int = 365,  # 1 year
    key_size: int = 4096,
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    """Generate a site certificate signed by CA.

    Args:
        ca_cert: CA certificate.
        ca_key: CA private key.
        common_name: Common name for the site certificate.
        organization: Organization name.
        country: Country code.
        validity_days: Certificate validity in days.
        key_size: RSA key size in bits.

    Returns:
        Tuple of (certificate, private key).
    """
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )

    # Build certificate
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )

    import datetime

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=validity_days))
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                key_cert_sign=False,
                key_agreement=False,
                content_commitment=False,
                data_encipherment=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage(
                [
                    x509.OID_SERVER_AUTH,
                    x509.OID_CLIENT_AUTH,
                ]
            ),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    return cert, private_key


def save_certificate(cert: x509.Certificate, path: str) -> None:
    """Save certificate to PEM file.

    Args:
        cert: Certificate to save.
        path: Output file path.
    """
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    logger.info(f"Certificate saved to {path}")


def save_private_key(key: rsa.RSAPrivateKey, path: str, password: bytes | None = None) -> None:
    """Save private key to PEM file.

    Args:
        key: Private key to save.
        path: Output file path.
        password: Optional password for encryption.
    """
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)

    if password:
        encryption: Any = serialization.BestAvailableEncryption(password)
    else:
        encryption = serialization.NoEncryption()

    with open(path, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=encryption,
            )
        )

    # Set restrictive permissions
    import os

    os.chmod(path, 0o600)

    logger.info(f"Private key saved to {path}")


def verify_certificate_chain(
    cert: x509.Certificate,
    ca_cert: x509.Certificate,
) -> bool:
    """Verify certificate is signed by CA.

    Args:
        cert: Certificate to verify.
        ca_cert: CA certificate.

    Returns:
        True if valid, False otherwise.
    """
    # Check issuer matches CA subject
    if cert.issuer != ca_cert.subject:
        logger.warning("Certificate issuer does not match CA subject")
        return False

    # Check not expired
    import datetime

    now = datetime.datetime.utcnow()
    if cert.not_valid_before > now or cert.not_valid_after < now:
        logger.warning("Certificate is expired or not yet valid")
        return False

    # Verify signature (simplified - full verification requires cryptography library)
    try:
        public_key = ca_cert.public_key()
        if isinstance(public_key, rsa.RSAPublicKey):
            public_key.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                padding=padding.PKCS1v15(),
                algorithm=hashes.SHA256(),
            )
        return True
    except Exception as e:
        logger.warning(f"Certificate signature verification failed: {e}")
        return False


__all__ = [
    "TLSConfig",
    "create_client_ssl_context",
    "create_ssl_context",
    "generate_ca_certificate",
    "generate_site_certificate",
    "load_private_key",
    "save_certificate",
    "save_private_key",
    "verify_certificate_chain",
]
