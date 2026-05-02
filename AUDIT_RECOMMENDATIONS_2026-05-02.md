# Slurm Heartbeat Audit Recommendations

Date: 2026-05-02

Scope: full repository review after the cleanup and the new EFP readiness publisher work. This is an audit only; no source code changes are recommended in this file as already-applied fixes.

## Executive Summary

The project is still useful as a small EFP-aligned readiness publisher, but it is not production-ready yet. The cleanup helped a lot: the package now has a `__main__.py`, `server.allowed_sites` is parsed, the Prometheus custom registry startup issue is fixed, the receiver has moved toward standard asyncio certificate extraction, and the test suite currently passes.

The main remaining risk is that the advertised publisher flow still breaks at runtime. `/readiness` depends on a readiness update path that currently raises a `TypeError`, `/metrics` awaits a synchronous object and also raises, and `--mode publisher` never starts the Slurm collection/normalization loop that would generate readiness in the first place.

## Verification Run

- `.cache/agent/venv/bin/python -m pytest -q`: passes, currently `100 passed, 2 warnings`.
- `.cache/agent/venv/bin/python -m ruff check .`: runs and reports one lint finding, `W293` blank line contains whitespace in [receiver.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/receiver.py:287).
- `.cache/agent/venv/bin/python -m slurmheartbeat --help`: works.
- `ClientConfig.load("config.example.yaml").server.allowed_sites`: now loads `["lumi", "leonardo", "mars", "efp-monitoring"]`.
- `ReadinessPublisher(ServerConfig(tls=TLSConfig(enabled=False)), "site", "cluster")`: now constructs successfully.
- `ReadinessPublisher.update_readiness(...)`: still fails with `TypeError: MetricsServer.record_readiness_update() missing 1 required positional argument: 'site'`.
- `ReadinessPublisher._handle_metrics(...)`: still fails with `TypeError: object CollectorRegistry can't be used in 'await' expression`.

## Critical Findings

1. **Readiness updates still crash before `/readiness` can serve fresh data.**

   [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:165) calls `record_readiness_update(readiness.status.value)`, but [metrics.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/monitoring/metrics.py:302) requires both `status` and `site`. Any heartbeat loop that reaches `self.publisher.update_readiness(readiness)` in [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:187) logs an exception and never updates the published readiness state reliably.

   Recommendation: pass `self.site_id` into `record_readiness_update`, then add a direct unit test for `ReadinessPublisher.update_readiness`.

2. **The aiohttp `/metrics` endpoint is broken.**

   [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:224) does `await self._metrics.get_metrics()`, but [metrics.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/monitoring/metrics.py:294) returns a synchronous `CollectorRegistry`, not text and not an awaitable. This causes `/metrics` on the publisher port to return a server error.

   Recommendation: choose one metrics serving model. Either remove the publisher `/metrics` route and rely on `prometheus_client.start_http_server`, or make `get_metrics()` return `generate_latest(self._registry).decode()` plus the proper Prometheus content type.

3. **`--mode publisher` starts a publisher with no readiness producer.**

   Collector and normalizer initialization is gated to `client`/`both` at [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:73), and the heartbeat loop is also gated to `client`/`both` at [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:133). In pure publisher mode, the server starts but never collects Slurm state or calls `update_readiness`, so `/readiness` stays `503` unless an external caller mutates state in-process.

   Recommendation: define publisher mode as "collect local Slurm state and publish it", or rename the current behavior to a passive mode. The EFP-aligned default should probably be publisher-first, not peer heartbeat-first.

4. **Publisher certificate identity extraction is still wrong for real aiohttp TLS transports.**

   [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:258) reads `peercert`, but if it receives the normal Python SSL certificate dictionary, [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:266) treats the dict as DER bytes and calls `x509.load_der_x509_certificate(cert)`. That raises and causes authorized mTLS callers to be rejected.

   Recommendation: reuse the simpler dict parsing now present in [receiver.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/receiver.py:277), and add a publisher test using an actual `peercert`-style dictionary.

## High Findings

5. **Metrics ownership and startup order are still muddled.**

   The publisher creates a default `MetricsServer()` in [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:82) before the daemon creates the configured metrics server in [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:104). Because `MetricsServer` is a singleton, this can lock in default config before the real Prometheus config is applied. The publisher also starts metrics at [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:102) while the daemon starts metrics again at [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:129).

   Recommendation: instantiate one configured `MetricsServer` in `HeartbeatDaemon`, pass it into publisher/receiver code, and start it exactly once.

6. **Readiness documents are documented as signed but are not signed by the publisher.**

   The README promises a signature at [README.md](/home/samehuman/projects/slurmheartbeat/README.md:26), and [schema.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/protocol/schema.py:234) has signing support. The publisher returns `readiness.to_dict()` directly at [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:212), so the readiness document is unsigned unless a caller pre-signed it.

   Recommendation: either make signing part of the publisher contract with configured signing keys, or explicitly document unsigned readiness for the current prototype.

7. **Important readiness signals are still hardcoded.**

   [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:180) passes `slurmctld_reachable=True` and [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:183) passes `maintenance=False`. That means controller outage and planned maintenance, two of the most important EFP readiness cases, can be reported incorrectly.

   Recommendation: derive reachability from collector failures or a lightweight controller check, and load maintenance intent from a local file, Slurm reservation convention, or site-provided endpoint.

8. **The collector still risks reinventing Slurm monitoring rather than consuming existing surfaces.**

   [collector.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/collector.py:3) says the collector supports OpenMetrics, `scontrol --json`, `sinfo`, `squeue`, and `slurmrestd`; the implementation only calls slurmrestd-style HTTP endpoints starting at [collector.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/collector.py:126). Slurm already exposes federation state and metrics that should be used before adding custom polling semantics.

   Recommendation: prioritize existing Slurm/EFP surfaces in this order: native Slurm federation state, Slurm OpenMetrics where available, `scontrol --json`/`sinfo --json` fallbacks, then custom readiness-only normalization. Keep this project as an adapter/contract layer, not a second monitoring system.

9. **The legacy peer heartbeat path is still active by default in `both` mode.**

   The default CLI mode is `both` at [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:283), and the heartbeat loop still creates and sends legacy peer messages at [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:206). The sender has no outgoing TLS configuration at [sender.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/sender.py:45), and receiver signatures are only verified when present at [receiver.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/receiver.py:334).

   Recommendation: keep legacy P2P behind an explicit feature flag with a disabled default until EFP confirms a push transport is needed. For the near-term EFP readiness use case, prefer pull-based `/readiness` over cross-site heartbeat fanout.

10. **Configuration and docs still describe more product surface than the code implements.**

    `config.example.yaml` includes root-level federation state, alerting, security, and performance sections at [config.example.yaml](/home/samehuman/projects/slurmheartbeat/config.example.yaml:89), [config.example.yaml](/home/samehuman/projects/slurmheartbeat/config.example.yaml:118), [config.example.yaml](/home/samehuman/projects/slurmheartbeat/config.example.yaml:148), and [config.example.yaml](/home/samehuman/projects/slurmheartbeat/config.example.yaml:167). Most of those options are not parsed or enforced by [config.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/config.py:125). The README also links to removed documents at [README.md](/home/samehuman/projects/slurmheartbeat/README.md:205), reports `95 tests passing` at [README.md](/home/samehuman/projects/slurmheartbeat/README.md:222) while the suite has 100 tests, and still uses placeholder repository/contact URLs at [README.md](/home/samehuman/projects/slurmheartbeat/README.md:53) and [README.md](/home/samehuman/projects/slurmheartbeat/README.md:302).

    Recommendation: either implement each advertised config field or remove it from the example. Keep docs aligned with the smaller readiness-publisher scope.

## Medium Findings

11. **Packaging advertises typed package data that is missing.**

    [pyproject.toml](/home/samehuman/projects/slurmheartbeat/pyproject.toml:64) includes `slurmheartbeat = ["py.typed"]`, but there is no `slurmheartbeat/py.typed` file. Type checkers will not see the package as typed after installation.

    Recommendation: add an empty `slurmheartbeat/py.typed` file if typed packaging is intended, or remove the package-data declaration.

12. **Dependencies include likely-unused libraries.**

    [pyproject.toml](/home/samehuman/projects/slurmheartbeat/pyproject.toml:33) and [requirements.txt](/home/samehuman/projects/slurmheartbeat/requirements.txt:3) include `pydantic`, but the code uses dataclasses and YAML parsing directly. The dev extras include `aiosmtplib` at [pyproject.toml](/home/samehuman/projects/slurmheartbeat/pyproject.toml:48), matching alerting docs more than current code.

    Recommendation: remove unused dependencies until the code actually imports them. This keeps the install surface smaller for HPC environments.

13. **Test coverage misses the exact publisher failures found by smoke testing.**

    The suite passes, but it does not catch the `update_readiness` metrics signature mismatch, the broken aiohttp `/metrics` handler, publisher-mode no-readiness behavior, or real `peercert` dict parsing in `ReadinessPublisher`.

    Recommendation: add small tests for those four paths before expanding features.

14. **Lint is almost clean but currently fails on one whitespace issue.**

    Running Ruff through the project-local venv reports `W293` at [receiver.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/receiver.py:287). This is trivial to fix, but it means the current tree is not lint-clean yet.

    Recommendation: remove the trailing whitespace-only blank line, then keep Ruff in CI or pre-commit so this stays automatic.

## Do Not Reinvent The Wheel

This codebase should stay narrow. Its useful niche is a stable, low-noise readiness contract for EFP consumers:

- Read native Slurm state rather than inventing federation state.
- Publish a compact readiness document rather than duplicating Prometheus/Grafana.
- Use Prometheus client/server behavior directly rather than wrapping it twice.
- Make transport security match standard mTLS behavior rather than inventing alternate certificate metadata conventions.
- Treat the push heartbeat system as experimental until a real EFP consumer requires it.

Existing tools and surfaces to lean on:

- Slurm Federation: `sacctmgr show federation`, `scontrol show federation`, FedState, cluster features.
- Slurm REST API (`slurmrestd`) for structured node, partition, and job state.
- Slurm OpenAPI/OpenMetrics support where available.
- Prometheus `prometheus_client` for metrics exposition.
- Existing site monitoring stacks for alerting, dashboards, and long-term history.

## Recommended Next Steps

1. Fix the two publisher runtime crashes: readiness metrics call and `/metrics` response generation.
2. Decide the mode model: make `publisher` actively collect and publish readiness, and move legacy peer push behind an opt-in flag.
3. Consolidate metrics ownership into one configured instance started once.
4. Implement real readiness inputs for controller reachability, maintenance intent, and federation visibility.
5. Align docs/config with what exists now; remove placeholder URLs and removed document links.
6. Add tests for publisher mode, mTLS `peercert` parsing, readiness signing behavior, and metrics exposition.
7. Only then add optional collector fallbacks for OpenMetrics and Slurm CLI JSON.

## References

- EuroHPC JU, "EuroHPC Federation Platform": https://www.eurohpc-ju.europa.eu/supercomputers/eurohpc-federation-platform_en
- EuroHPC JU, "First release of the EuroHPC Federation Platform", 2026-04-15: https://www.eurohpc-ju.europa.eu/first-release-eurohpc-federation-platform-streamline-access-europes-supercomputing-resources-2026-04-15_en
- SchedMD, "Slurm REST API": https://slurm.schedmd.com/rest.html
- SchedMD, "Slurm Federated Scheduling Guide": https://slurm.schedmd.com/federation.html
- SchedMD, "Slurm OpenAPI Plugins": https://slurm.schedmd.com/openapi.html
