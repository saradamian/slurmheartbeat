# Slurm Heartbeat Audit Recommendations

Date: 2026-05-04

Scope: full repository audit after the latest implementation pass. This review checks whether the new work actually closes the prior findings, whether the codebase is still useful without reinventing existing Slurm/Prometheus functionality, and whether dead or misleading code/docs remain. Source code was not edited.

## Executive Summary

The codebase is useful as a narrow EFP-facing readiness adapter: it can collect coarse Slurm state, normalize that into a small readiness document, and serve it behind mTLS. That is the right shape. It should not grow into a replacement for Slurm federation, a scheduler, a Prometheus stack, or a site alerting system.

The latest implementation fixed several earlier issues: the daemon now initializes collector/normalizer in publisher mode, nested stdlib certificate subjects are handled in the main publisher/receiver dict paths, legacy P2P is disabled by default, unused `pydantic`/`aiosmtplib` dependencies are gone, and `slurmheartbeat/py.typed` now exists.

It is still not production-ready. The current blockers are narrower but important: metrics can still double-start, publisher-mode readiness updates are still gated by `client.enabled`, readiness signing is configured in code but not in YAML and currently fails at runtime, controller reachability is inferred from node count rather than collection health, and several docs/changelog claims say items are fixed when they are not.

## Verification Run

- `.cache/agent/venv/bin/python -m pytest -q`: `106 passed, 2 warnings`.
- `env RUFF_CACHE_DIR=/tmp/slurmheartbeat-ruff-cache .cache/agent/venv/bin/python -m ruff check .`: `All checks passed!`.
- `.cache/agent/venv/bin/python -m slurmheartbeat --help`: works.
- `.cache/agent/venv/bin/python -m mypy slurmheartbeat --cache-dir /tmp/slurmheartbeat-mypy-cache`: fails with `85 errors in 8 files`.
- `MetricsServer.start()` called twice on the same instance calls `start_http_server()` twice.
- `ReadinessMessage.sign(load_private_key(...))`: raises `TypeError`, matching the publisher signing path.
- `ClientConfig.load("config.example.yaml").server.allowed_sites`: returns four configured sites.
- `ClientConfig.load("config.example.yaml").server.enable_legacy_p2p`: returns `False`.
- `hasattr(ClientConfig.load("config.example.yaml").server, "peer_public_keys")`: returns `False` because the example only comments the keys out.

## Critical Findings

1. **Metrics can still double-start and can ignore `prometheus.enabled=false`.**

   [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:74) starts `self.metrics` before the publisher, but [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:105) still starts its metrics instance again. `MetricsServer.start()` has no idempotence guard before [metrics.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/monitoring/metrics.py:177), so a double call invokes `prometheus_client.start_http_server()` twice and can fail with an address already in use.

   There is a second lifecycle mismatch: [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:99) passes `metrics=None` when Prometheus is disabled, and [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:85) then creates a default enabled `MetricsServer()`. That means disabling Prometheus in config may not actually disable the publisher's metrics server.

   Recommendation: make metrics ownership explicit. Either the daemon starts one `MetricsServer` and the publisher only exposes `get_metrics()`, or the publisher owns metrics and `main.py` never starts it. Add an idempotence guard in `MetricsServer.start()`, and pass a disabled metrics object when Prometheus is disabled instead of letting the publisher create defaults.

2. **Publisher-mode readiness updates still stop when `client.enabled=false`.**

   [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:82) correctly initializes the collector/normalizer for publisher mode, but [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:142) only starts `_heartbeat_loop()` if [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:143) sees `self.config.client.enabled`. That loop is the only path that calls [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:207), `self.publisher.update_readiness(readiness)`.

   In other words, a site can run `--mode publisher` with outgoing client heartbeats disabled and still serve `/readiness`, but it will never publish fresh readiness.

   Recommendation: rename/split the loop into a local readiness collection loop and an outgoing heartbeat send path. `client.enabled` should only gate `HeartbeatSender`, not local Slurm collection or publisher updates.

3. **Readiness signing is still not functional through the daemon.**

   [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:58) accepts `signing_key_file`, and [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:219) attempts to sign before serving `/readiness`. But [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:100) never passes a signing key from config, and `ServerConfig` has no signing key field at [config.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/config.py:65).

   Even if a caller manually passes `signing_key_file`, [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:222) loads an `RSAPrivateKey` object and [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:224) passes it to [schema.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/protocol/schema.py:234), whose `ReadinessMessage.sign()` expects PEM bytes and calls `serialization.load_pem_private_key()`. The publisher catches the exception at [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:226) and serves an unsigned document anyway.

   Recommendation: choose one signing API and wire it end to end. Prefer a typed `server.signing_key_file` config field, pass it from `main.py`, and either make `ReadinessMessage.sign()` accept key objects like legacy `HeartbeatMessage.sign()` or pass PEM bytes. Decide whether unsigned readiness should be an explicit config mode; do not silently fail open while docs promise signatures.

4. **Controller reachability is inferred from node count, not collection health.**

   The double Slurm collection is gone from the main loop, which is good. But [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:191) now sets `slurmctld_reachable` to true only when `metrics.node_stats.total > 0`. That conflates API health with cluster shape. A healthy test/dev Slurm with zero visible nodes, a permission-filtered response, or a transient parser issue can be reported as controller-unreachable; conversely the collector still has no explicit health status.

   [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:292) also leaves `_check_slurmctld_reachable()` in place, but it is now unused and would still treat any non-raising empty `collect()` call as reachable.

   Recommendation: make `SlurmCollector.collect()` return a typed result with both `metrics` and `collection_health`, or add a dedicated lightweight Slurm API health probe. Remove `_check_slurmctld_reachable()` once the new health signal exists.

## High Findings

5. **Legacy P2P is disabled by default, but its config/security story is incomplete.**

   [config.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/config.py:76) adds `enable_legacy_p2p: bool = False`, and [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:113) respects it. However, [config.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/config.py:213) does not parse `enable_legacy_p2p` from YAML, so operators cannot enable it through `config.example.yaml`.

   If legacy P2P is enabled through code, [receiver.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/receiver.py:165) still allows all members when the allowlist is empty, and [receiver.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/receiver.py:319) verifies signatures only if a signature is present. Unsigned heartbeats from an mTLS-authorized peer are accepted.

   Recommendation: either remove legacy P2P from the default product until EFP requires push transport, or wire it as an explicit, documented config mode with fail-closed allowlists and a clear `require_signatures` policy.

6. **Peer public keys are attached dynamically instead of being typed config.**

   [config.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/config.py:269) reads top-level `federation.peer_public_keys` and then dynamically creates `config.server.peer_public_keys` at [config.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/config.py:273). [receiver.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/receiver.py:245) depends on that dynamic attribute.

   This works at runtime only when keys are actually configured, but it is invisible to the `ServerConfig` dataclass and contributes to the mypy failures at [config.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/config.py:274). It is also easy for tests and future maintainers to miss.

   Recommendation: add `peer_public_keys: dict[str, str]` to `ServerConfig`, parse it normally, and remove the `hasattr` mutation.

7. **Prometheus exposition is duplicated.**

   [metrics.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/monitoring/metrics.py:177) starts a standalone Prometheus HTTP server, while [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:101) also exposes `/metrics` through the aiohttp readiness publisher. Both are backed by the same registry, but the deployment model is ambiguous and the double-start bug comes from this split ownership.

   Recommendation: do not reinvent Prometheus serving twice. Pick one surface: either a dedicated Prometheus port via `prometheus_client.start_http_server()`, or the publisher's `/metrics` route. Document that choice and remove the other path.

8. **The project still claims more production readiness than the code supports.**

   [README.md](/home/samehuman/projects/slurmheartbeat/README.md:210) says `PRODUCTION READY` and "All 12 audit findings resolved". Several rows below that are false in the current code: metrics double-starting is not fixed at [README.md](/home/samehuman/projects/slurmheartbeat/README.md:228), readiness signing is not actually functional through the daemon at [README.md](/home/samehuman/projects/slurmheartbeat/README.md:229), and `client.enabled=false` still blocks publisher updates despite [CHANGELOG.md](/home/samehuman/projects/slurmheartbeat/CHANGELOG.md:25).

   [IMPLEMENTATION_SUMMARY.md](/home/samehuman/projects/slurmheartbeat/IMPLEMENTATION_SUMMARY.md:4) and [FINAL_VERIFICATION_REPORT.md](/home/samehuman/projects/slurmheartbeat/FINAL_VERIFICATION_REPORT.md:4) also say `PRODUCTION READY`, adding more documents that can drift from reality.

   Recommendation: change the status language to "prototype" or "alpha readiness adapter" until the daemon lifecycle/security blockers are fixed. Keep one living audit/status file; make old implementation reports historical or remove them.

## Medium Findings

9. **The example config still contains unimplemented sections.**

   [config.example.yaml](/home/samehuman/projects/slurmheartbeat/config.example.yaml:96) includes federation state persistence and thresholds that are not parsed. [config.example.yaml](/home/samehuman/projects/slurmheartbeat/config.example.yaml:122) includes webhook/email alerting details, [config.example.yaml](/home/samehuman/projects/slurmheartbeat/config.example.yaml:152) includes security/rotation/access-control settings, and [config.example.yaml](/home/samehuman/projects/slurmheartbeat/config.example.yaml:171) includes performance/compression/resource settings. Most of these are not implemented by [config.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/config.py:137).

   Recommendation: keep the deployable example to implemented keys only. Move aspirational options into ADRs or roadmap docs so operators do not assume they work.

10. **Maintenance mode remains hardcoded despite documentation saying it is configurable.**

    [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:316) checks only `/var/run/slurm/heartbeat/maintenance`. [CHANGELOG.md](/home/samehuman/projects/slurmheartbeat/CHANGELOG.md:39) says the maintenance file path is configurable, but no such field exists in `GeneralConfig`, `ServerConfig`, or `MonitoringConfig`.

    Recommendation: either add `general.maintenance_file` and parse it, or document the hardcoded file as the current contract.

11. **Type checking is configured but not passing.**

    [pyproject.toml](/home/samehuman/projects/slurmheartbeat/pyproject.toml:114) enables strict-ish mypy settings, and `slurmheartbeat/py.typed` now exists. The actual run still fails with 85 errors. Important ones overlap real design issues: dynamic `ServerConfig.peer_public_keys`, `ReadinessMessage.sign()` key-type mismatch, cryptography key unions, `client.config.PrometheusConfig` being a different class than `monitoring.metrics.PrometheusConfig`, and a possible `None` access in [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:251).

    Recommendation: either make mypy part of CI and fix the typed API boundaries, or relax/remove the advertised strict type posture until it is true.

12. **Tests pass but miss the highest-risk lifecycle cases.**

    The test suite is valuable, but current tests do not catch: double-starting metrics, `prometheus.enabled=false` still creating default metrics in the publisher, publisher mode with `client.enabled=false`, YAML parsing for `enable_legacy_p2p`, runtime readiness signing with `signing_key_file`, or accepting unsigned legacy heartbeats.

    Recommendation: add small regression tests for the smoke probes in this audit before adding broader features.

13. **Some docs still overstate Slurm input support.**

    [collector.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/collector.py:1) now honestly says the implementation uses `slurmrestd`, but [README.md](/home/samehuman/projects/slurmheartbeat/README.md:46) still says "REST API or OpenMetrics support". The project does not currently scrape Slurm OpenMetrics directly.

    Recommendation: describe `slurmrestd` as the only implemented data source. Keep OpenMetrics, `scontrol --json`, and `sinfo/squeue` as future input adapters if needed.

14. **Repository metadata is partly fixed but still inconsistent.**

    [README.md](/home/samehuman/projects/slurmheartbeat/README.md:53) points to `samehuman/slurmheartbeat`, but the configured remote is `saradamian/slurmheartbeat`. [pyproject.toml](/home/samehuman/projects/slurmheartbeat/pyproject.toml:53) also uses `samehuman/slurmheartbeat`, and [CHANGELOG.md](/home/samehuman/projects/slurmheartbeat/CHANGELOG.md:259) still has a `your-org` release URL.

    Recommendation: update all URLs to the actual repository before publishing packages or docs.

## Dead Code / Drift Watchlist

- [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:292): `_check_slurmctld_reachable()` is unused after the single-collection refactor.
- [receiver.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/receiver.py:223): legacy P2P receiver is not started by default; keep it only if there is an actual EFP push-use case.
- [IMPLEMENTATION_SUMMARY.md](/home/samehuman/projects/slurmheartbeat/IMPLEMENTATION_SUMMARY.md:1) and [FINAL_VERIFICATION_REPORT.md](/home/samehuman/projects/slurmheartbeat/FINAL_VERIFICATION_REPORT.md:1): duplicate status reports are already stale.
- [config.example.yaml](/home/samehuman/projects/slurmheartbeat/config.example.yaml:96): large unparsed config areas are effectively dead configuration surface.

## Do Not Reinvent The Wheel

The useful product here is a narrow readiness contract: "Can this site safely receive federated work right now?" Keep the implementation small and boring.

- Use native Slurm federation state (`sacctmgr show federation`, `scontrol show federation`, FedState, cluster features) instead of building a parallel federation model.
- Use Slurm REST/OpenAPI or native Slurm OpenMetrics where already deployed; if OpenMetrics is desired, add it as an input adapter rather than inventing a custom metrics model.
- Let Prometheus tooling own scraping, storage, dashboards, and alerting. This project should expose a few useful gauges, not become an observability stack.
- Let site monitoring stacks own notifications, certificate-expiry alerts, and operational dashboards.
- Keep `/readiness` as a coarse operational contract. Avoid user/job/account detail and avoid making placement decisions.
- Treat legacy peer heartbeat push as optional until an EFP consumer explicitly needs it.

## Recommended Next Steps

1. Fix metrics ownership: one metrics instance, one start path, disabled config respected.
2. Decouple publisher readiness updates from `client.enabled`.
3. Wire readiness signing through typed YAML config and make signing fail policy explicit.
4. Replace node-count reachability with explicit collection health.
5. Decide whether legacy P2P remains; if yes, parse `enable_legacy_p2p`, add typed peer keys, and require signatures when configured.
6. Trim `config.example.yaml` to implemented settings.
7. Replace `PRODUCTION READY` claims with alpha/prototype status until the blockers are closed.
8. Add targeted tests for the lifecycle/security cases above.
9. Fix or de-scope mypy so the typed-package claim means something.

## References

- EuroHPC JU, "EuroHPC Federation Platform": https://www.eurohpc-ju.europa.eu/supercomputers/eurohpc-federation-platform_en
- EuroHPC JU, "First release of the EuroHPC Federation Platform", 2026-04-15: https://www.eurohpc-ju.europa.eu/first-release-eurohpc-federation-platform-streamline-access-europes-supercomputing-resources-2026-04-15_en
- SchedMD, "Slurm REST API": https://slurm.schedmd.com/rest.html
- SchedMD, "Slurm Federated Scheduling Guide": https://slurm.schedmd.com/federation.html
- SchedMD, "Slurm OpenAPI Plugins": https://slurm.schedmd.com/openapi.html
