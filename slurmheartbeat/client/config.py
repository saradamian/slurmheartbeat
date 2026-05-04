"""Client configuration loader."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class SlurmConfig:
    """Slurm API configuration."""

    api_url: str = "http://localhost:6820"
    api_version: str = "0.0.39"
    timeout: int = 5


@dataclass
class PeerConfig:
    """Federation peer configuration."""

    name: str
    endpoint: str
    site: str
    timeout_seconds: int = 30


@dataclass
class FederationConfig:
    """Federation configuration."""

    peers: list[PeerConfig] = field(default_factory=list)
    peer_public_keys: dict[str, str] = field(default_factory=dict)


@dataclass
class HeartbeatClientConfig:
    """Client heartbeat configuration."""

    enabled: bool = True
    interval_seconds: int = 10
    timeout_seconds: int = 30
    retry_count: int = 3
    retry_backoff: float = 2.0
    slurm: SlurmConfig = field(default_factory=SlurmConfig)
    federation: FederationConfig = field(default_factory=FederationConfig)
    tls: TLSConfig | None = None  # Client TLS for mTLS and signing


@dataclass
class TLSConfig:
    """TLS configuration."""

    enabled: bool = True
    cert_file: str = "/etc/slurm/heartbeat/cert.pem"
    key_file: str = "/etc/slurm/heartbeat/key.pem"
    ca_file: str = "/etc/slurm/heartbeat/ca.pem"
    client_auth: str = "required"
    min_version: str = "1.3"
    max_version: str = "1.3"


@dataclass
class ServerConfig:
    """Server configuration."""

    enabled: bool = True
    listen_address: str = "0.0.0.0"
    listen_port: int = 8443
    tls: TLSConfig = field(default_factory=TLSConfig)
    max_connections: int = 100
    connection_timeout: int = 30
    allowed_sites: list[str] = field(default_factory=list)


@dataclass
class PrometheusConfig:
    """Prometheus metrics configuration."""

    enabled: bool = True
    port: int = 9090
    path: str = "/metrics"
    listen_address: str = "0.0.0.0"


@dataclass
class AlertingConfig:
    """Alerting configuration."""

    enabled: bool = True
    webhook_url: str | None = None
    webhook_timeout: int = 10
    email_enabled: bool = False
    email_recipients: list[str] = field(default_factory=list)


@dataclass
class MonitoringConfig:
    """Monitoring configuration."""

    prometheus: PrometheusConfig = field(default_factory=PrometheusConfig)
    alerting: AlertingConfig = field(default_factory=AlertingConfig)


@dataclass
class ClusterInfo:
    """Local cluster information."""

    id: str = "unknown"
    name: str = "unknown"
    site: str = "unknown"


@dataclass
class GeneralConfig:
    """General configuration."""

    log_level: str = "INFO"
    log_file: str = "/var/log/slurm/heartbeat.log"
    pid_file: str = "/var/run/slurm/heartbeat.pid"
    daemonize: bool = False


@dataclass
class ClientConfig:
    """Complete client configuration."""

    general: GeneralConfig = field(default_factory=GeneralConfig)
    client: HeartbeatClientConfig = field(default_factory=HeartbeatClientConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    cluster: ClusterInfo = field(default_factory=ClusterInfo)

    @classmethod
    def load(cls, config_path: str | Path) -> ClientConfig:
        """Load configuration from YAML file.

        Args:
            config_path: Path to configuration file.

        Returns:
            Loaded configuration.
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path) as f:
            data = yaml.safe_load(f)

        config = cls()

        # Parse general section
        if "general" in data:
            general_data = data["general"]
            config.general = GeneralConfig(
                log_level=general_data.get("log_level", "INFO"),
                log_file=general_data.get("log_file", "/var/log/slurm/heartbeat.log"),
                pid_file=general_data.get("pid_file", "/var/run/slurm/heartbeat.pid"),
                daemonize=general_data.get("daemonize", False),
            )

        # Parse client section
        if "client" in data:
            client_data = data["client"]
            # Parse client TLS config if present
            client_tls_data = client_data.get("tls", {})
            client_tls = None
            if client_tls_data:
                client_tls = TLSConfig(
                    enabled=client_tls_data.get("enabled", True),
                    cert_file=client_tls_data.get("cert_file", "/etc/slurm/heartbeat/cert.pem"),
                    key_file=client_tls_data.get("key_file", "/etc/slurm/heartbeat/key.pem"),
                    ca_file=client_tls_data.get("ca_file", "/etc/slurm/heartbeat/ca.pem"),
                    client_auth=client_tls_data.get("client_auth", "required"),
                    min_version=client_tls_data.get("min_version", "1.3"),
                    max_version=client_tls_data.get("max_version", "1.3"),
                )

            config.client = HeartbeatClientConfig(
                enabled=client_data.get("enabled", True),
                interval_seconds=client_data.get("interval_seconds", 10),
                timeout_seconds=client_data.get("timeout_seconds", 30),
                retry_count=client_data.get("retry_count", 3),
                retry_backoff=client_data.get("retry_backoff", 2.0),
                slurm=SlurmConfig(
                    api_url=client_data.get("slurm", {}).get("api_url", "http://localhost:6820"),
                    api_version=client_data.get("slurm", {}).get("api_version", "0.0.39"),
                    timeout=client_data.get("slurm", {}).get("timeout", 5),
                ),
                federation=FederationConfig(
                    peers=[
                        PeerConfig(
                            name=p["name"],
                            endpoint=p["endpoint"],
                            site=p["site"],
                            timeout_seconds=p.get("timeout_seconds", 30),
                        )
                        for p in client_data.get("federation", {}).get("peers", [])
                    ],
                    peer_public_keys=client_data.get("federation", {}).get("peer_public_keys", {}),
                ),
                tls=client_tls,
            )

        # Parse server section
        if "server" in data:
            server_data = data["server"]
            tls_data = server_data.get("tls", {})
            config.server = ServerConfig(
                enabled=server_data.get("enabled", True),
                listen_address=server_data.get("listen_address", "0.0.0.0"),
                listen_port=server_data.get("listen_port", 8443),
                tls=TLSConfig(
                    enabled=tls_data.get("enabled", True),
                    cert_file=tls_data.get("cert_file", "/etc/slurm/heartbeat/cert.pem"),
                    key_file=tls_data.get("key_file", "/etc/slurm/heartbeat/key.pem"),
                    ca_file=tls_data.get("ca_file", "/etc/slurm/heartbeat/ca.pem"),
                    client_auth=tls_data.get("client_auth", "required"),
                    min_version=tls_data.get("min_version", "1.3"),
                    max_version=tls_data.get("max_version", "1.3"),
                ),
                max_connections=server_data.get("max_connections", 100),
                connection_timeout=server_data.get("connection_timeout", 30),
                allowed_sites=server_data.get("allowed_sites", []),
            )

        # Parse monitoring section
        if "monitoring" in data:
            mon_data = data["monitoring"]
            prom_data = mon_data.get("prometheus", {})
            alert_data = mon_data.get("alerting", {})
            webhook_data = alert_data.get("webhook", {})
            email_data = alert_data.get("email", {})
            config.monitoring = MonitoringConfig(
                prometheus=PrometheusConfig(
                    enabled=prom_data.get("enabled", True),
                    port=prom_data.get("port", 9090),
                    path=prom_data.get("path", "/metrics"),
                    listen_address=prom_data.get("listen_address", "0.0.0.0"),
                ),
                alerting=AlertingConfig(
                    enabled=alert_data.get("enabled", True),
                    webhook_url=webhook_data.get("url"),
                    webhook_timeout=webhook_data.get("timeout", 10),
                    email_enabled=email_data.get("enabled", False),
                    email_recipients=email_data.get("recipients", []),
                ),
            )

        # Parse cluster info
        if "cluster" in data:
            cluster_data = data["cluster"]
            config.cluster = ClusterInfo(
                id=cluster_data.get("id", "unknown"),
                name=cluster_data.get("name", "unknown"),
                site=cluster_data.get("site", "unknown"),
            )

        # Parse top-level federation section for peer_public_keys only
        # Do NOT overwrite server.allowed_sites - keep them separate
        if "federation" in data:
            fed_data = data["federation"]
            # Only load peer_public_keys for signature verification
            if "peer_public_keys" in fed_data:
                config.client.federation.peer_public_keys = fed_data.get("peer_public_keys", {})

        return config
