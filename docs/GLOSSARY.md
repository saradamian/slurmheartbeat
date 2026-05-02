# Slurm Heartbeat - Glossary

## A

**ADR (Architecture Decision Record)**
A document that records a significant architectural decision made for the project, including context, decision, and consequences.

**Alerting**
The process of notifying operators when certain conditions are met (e.g., peer down, high latency).

**API (Application Programming Interface)**
A set of rules and protocols for building and interacting with software applications. In this project, primarily the Slurm REST API.

**Authentication**
The process of verifying the identity of a user, system, or component. This project uses mutual TLS (mTLS) for authentication.

**Authorization**
The process of determining what an authenticated entity is allowed to do. This project uses access control lists (ACLs) for authorization.

## B

**Backoff**
A strategy for retrying failed operations with increasing delays between attempts. This project uses exponential backoff for heartbeat retries.

**Blocker**
A finding in code review that must be addressed before the code can be merged (e.g., security vulnerability, critical bug).

## C

**CA (Certificate Authority)**
An entity that issues digital certificates. In EFP, a central CA issues certificates for all federation members.

**Certificate (TLS/SSL)**
A digital document that verifies the identity of a device or system. Used for TLS encryption and authentication.

**CI/CD (Continuous Integration/Continuous Deployment)**
Automated processes for building, testing, and deploying code changes.

**CN (Common Name)**
A field in a certificate's subject that typically identifies the hostname or site name.

**CRITICAL**
The highest severity level for alerts, indicating an immediate issue requiring attention.

## D

**Daemon**
A background process that runs continuously, performing system tasks. The heartbeat daemon runs on each Slurm site.

**Degraded**
A peer status indicating reduced functionality (e.g., missed 2 heartbeats but not yet down).

**Denial of Service (DoS)**
An attack that makes a service unavailable to legitimate users. This project implements rate limiting to mitigate DoS.

**Derivative Work**
A work based on the original work (e.g., modifications, translations). Governed by the Apache License 2.0.

**Down**
A peer status indicating the peer is unreachable (e.g., missed 3+ heartbeats).

## E

**EFP (European Federated Platform)**
The EuroHPC Federation Platform, an initiative to federate HPC resources across the European Union.

**EKU (Extended Key Usage)**
A certificate extension that specifies the purposes for which a certificate can be used (e.g., clientAuth, serverAuth).

**Endpoint**
A network address (URL) where a service can be accessed. In this project, the heartbeat endpoint is typically `https://site:8443/heartbeat`.

**Escalation**
The process of raising an issue to a higher level of support when it cannot be resolved at the current level.

**Exponential Backoff**
A retry strategy where the delay between retries increases exponentially (e.g., 1s, 2s, 4s, 8s).

## F

**Federation**
A group of interconnected systems that work together as a single entity. In this project, a federation of Slurm clusters.

**Federation Member**
A site or cluster that is part of the federation.

**Firewall**
A network security system that controls incoming and outgoing network traffic based on security rules.

**Forward Secrecy**
A property of TLS that ensures past communications remain secure even if long-term keys are compromised.

## G

**Gauge**
A Prometheus metric type that represents a single numerical value that can go up and down (e.g., peer status).

**GDPR (General Data Protection Regulation)**
EU regulation on data protection and privacy. Relevant for cross-border data transfers in EFP.

**Git**
A distributed version control system used for source code management.

**Grafana**
A visualization platform often used with Prometheus for creating dashboards.

## H

**HA (High Availability)**
Systems designed to remain operational with minimal downtime.

**Handshake**
The process of establishing a secure TLS connection between client and server.

**Heartbeat**
A periodic message sent to indicate that a system is alive and functioning.

**Histogram**
A Prometheus metric type that samples observations and counts them in configurable buckets (e.g., latency).

**HPC (High Performance Computing)**
The practice of aggregating computing power to perform complex calculations at high speeds.

## I

**ID (Identifier)**
A unique value used to identify an entity (e.g., cluster ID, job ID).

**Integration Test**
A test that verifies the interaction between multiple components.

**IP (Internet Protocol)**
The principal communications protocol for relaying datagrams across network boundaries.

**iptables**
A user-space utility program that allows configuration of Linux kernel firewall rules.

## J

**Job (Slurm)**
A unit of work submitted to the Slurm workload manager for execution.

**Journal (systemd)**
The system logging service in systemd, accessible via `journalctl`.

## K

**Key (Private/Public)**
Cryptographic keys used in asymmetric encryption. The private key is kept secret; the public key is shared.

**Key Usage**
A certificate extension that specifies the cryptographic operations the certificate can be used for (e.g., digitalSignature, keyEncipherment).

## L

**Latency**
The time delay between sending and receiving a message. Measured in milliseconds or seconds.

**License (Apache 2.0)**
The open-source license under which this project is distributed.

**Log**
A record of events, errors, or activities generated by a system.

**LUMI**
One of the supercomputers in the EFP, located in Finland.

## M

**mTLS (Mutual TLS)**
A security approach where both client and server authenticate each other using certificates.

**Metrics**
Quantifiable measurements of system performance and health.

**MR (Merge Request)**
A GitLab feature for proposing and reviewing code changes (similar to Pull Request in GitHub).

**Mypy**
A static type checker for Python code.

## N

**Namespace**
A container for organizing code (e.g., Python packages).

**NIT**
A low-priority finding in code review, typically style or minor improvements.

**Node**
A compute server in a Slurm cluster.

## O

**OCSP (Online Certificate Status Protocol)**
A protocol for checking the revocation status of certificates.

**Operations (Ops)**
The team or processes responsible for running and maintaining the system in production.

**OU (Organizational Unit)**
A field in a certificate's subject that identifies the organization or department.

## P

**PEM (Privacy Enhanced Mail)**
A file format for storing cryptographic keys and certificates (Base64-encoded).

**Peer**
A federation member that exchanges heartbeat messages with other members.

**Performance Test**
A test that measures system performance under load.

**PID (Process ID)**
A unique identifier for a running process.

**PKI (Public Key Infrastructure)**
A system for managing digital certificates and public-key encryption.

**POC (Proof of Concept)**
A preliminary implementation to validate feasibility.

**Prometheus**
An open-source monitoring and alerting toolkit.

**PR (Pull Request)**
A GitHub feature for proposing and reviewing code changes (similar to Merge Request in GitLab).

**Private Key**
A cryptographic key kept secret, used for decryption and signing.

**Process**
A running instance of a program.

**Production**
The live environment where the system serves real users.

**Protocol**
A set of rules governing data exchange between systems.

**Proxy**
An intermediary server that forwards requests and responses.

**Public Key**
A cryptographic key that can be shared, used for encryption and verification.

## Q

**Quantum Computing**
A type of computing that uses quantum mechanics principles. Part of EFP's scope.

**Queue**
A data structure for storing pending jobs in Slurm.

## R

**Rate Limiting**
Restricting the number of requests a client can make in a given time period.

**Rebase**
A Git operation to integrate changes from one branch into another.

**REST (Representational State Transfer)**
An architectural style for APIs. Slurm provides a REST API.

**Retry**
The act of attempting an operation again after failure.

**RFC (Request for Comments)**
A document describing internet standards and protocols.

**Root Cause Analysis**
The process of identifying the underlying cause of an issue.

**Runbook**
A document with step-by-step procedures for operational tasks.

## S

**SAN (Subject Alternative Name)**
A certificate extension that allows specifying multiple hostnames/IPs for a single certificate.

**Schema**
A definition of the structure and constraints of data (e.g., JSON schema).

**Secret**
Sensitive information that must be protected (e.g., private keys, passwords).

**Security**
Protection against unauthorized access, use, or damage.

**Service**
A running process that provides functionality (e.g., systemd service).

**SHA (Secure Hash Algorithm)**
A family of cryptographic hash functions.

**Slurm**
A workload manager for Linux clusters.

**Slurmctld**
The Slurm controller daemon that manages the cluster.

**SSL (Secure Sockets Layer)**
Predecessor to TLS, still commonly used to refer to TLS.

**State**
The current condition or status of a system or peer.

**Status**
The current state of a peer (healthy, degraded, down).

**Staging**
A pre-production environment for testing changes.

**Systemd**
A system and service manager for Linux.

## T

**TLS (Transport Layer Security)**
A cryptographic protocol for secure communication. Version 1.3 is the current standard.

**TODO**
A task or item that needs to be completed.

**Topology**
The arrangement of elements in a network or system.

**Trace**
A record of execution flow for debugging.

**Transaction**
A unit of work that is either completed entirely or not at all.

**Transport**
The method of data transmission (e.g., TCP, UDP).

**Troubleshooting**
The process of identifying and resolving issues.

**TS (TypeScript)**
A typed superset of JavaScript. Not used in this project (Python).

## U

**UDP (User Datagram Protocol)**
A connectionless transport protocol. Not used for heartbeats (TCP/HTTPS preferred).

**Unit Test**
A test of individual components in isolation.

**URL (Uniform Resource Locator)**
A reference to a web resource (e.g., `https://site:8443/heartbeat`).

**UUID (Universally Unique Identifier)**
A 128-bit number used to identify information.

## V

**Validation**
The process of checking if data meets requirements.

**Version Control**
A system for managing changes to source code (e.g., Git).

**Virtual Environment**
An isolated Python environment for dependency management.

## W

**Webhook**
A method for one system to notify another of events via HTTP callbacks.

**Workflow**
A sequence of steps to accomplish a task.

## X

**X.509**
A standard for public key certificates, used in TLS.

## Y

**YAML (YAML Ain't Markup Language)**
A human-readable data serialization format used for configuration files.

## Z

**Zero Trust**
A security model that assumes no implicit trust, even within the network perimeter.
