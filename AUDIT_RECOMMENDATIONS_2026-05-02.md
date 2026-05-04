# Slurm Heartbeat Audit Recommendations

Date: 2026-05-04

Scope: full repository audit after the latest implementation pass. This review checks whether the new work actually closes the prior findings, whether the codebase is still useful without reinventing existing Slurm/Prometheus functionality, and whether dead or misleading code/docs remain. Source code was not edited.

## Executive Summary

The codebase is moving in the right direction as an EFP-facing readiness adapter. The latest changes fixed some important issues: client TLS config is now parsed, heartbeat signing accepts key objects, signing failures fail closed, `server.allowed_sites` survives config loading, receiver allowlists are initialized from config, Ruff is clean, and the test suite passes.

It is still not production-ready. The most important blockers are now narrower but real: the daemon still wires metrics in the wrong order and can double-start Prometheus, publisher and receiver certificate parsing still fail for the standard nested `ssl.getpeercert()` subject shape, publisher readiness generation can still be disabled by `client.enabled=false`, and the new reachability check can report true while the collector returned empty fallback metrics.

## Verification Run

- `.cache/agent/venv/bin/python -m pytest -q`: `106 passed, 2 warnings`.
- `.cache/agent/venv/bin/python -m ruff check .`: `All checks passed!`.
- `.cache/agent/venv/bin/python -m slurmheartbeat --help`: works.
- `.cache/agent/venv/bin/python -m mypy slurmheartbeat`: fails with a mypy internal error in this environment.
- `ClientConfig.load("config.example.yaml").client.tls`: present and enabled.
- `ClientConfig.load("config.example.yaml").server.allowed_sites`: returns `["lumi", "leonardo", "mars", "efp-monitoring"]`.
- `HeartbeatReceiver(ClientConfig.load("config.example.yaml").server).state._allowed_members`: contains the four configured allowed sites.
- `HeartbeatMessage.sign(key_object)`: succeeds.
- `ReadinessPublisher._extract_peer_name()` with simplified `("commonName", "test-cluster")` subject shape: succeeds.
- `ReadinessPublisher._extract_peer_name()` with normal nested `((("commonName", "test-cluster"),),)` subject shape: returns `None`.
- Creating a `ReadinessPublisher` before `MetricsServer(PrometheusConfig(port=9999))`: the singleton keeps port `9090`, showing configured metrics can still be lost.

## Critical Findings

1. **Metrics are still initialized in the wrong order and can double-start.**

   [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:91) creates the publisher before [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:110) creates the configured metrics server. The publisher receives `metrics=self.metrics` at [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:99), but `self.metrics` is still `None`, so [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:82) creates a default singleton `MetricsServer()`. Later `MetricsServer(self.config.monitoring.prometheus)` returns that same already-initialized object, so non-default Prometheus config can be ignored. The publisher also starts metrics at [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:102), and the daemon starts metrics again at [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:127).

   Recommendation: instantiate `self.metrics` before `ReadinessPublisher`, pass the actual configured object, and start metrics in exactly one place. If the publisher owns `/metrics`, remove `start_http_server()` from the daemon path.

2. **mTLS peer-name extraction still fails for the standard nested certificate subject shape.**

   The publisher parser at [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:269) only handles flattened tuples like `("commonName", "site")`. Python `ssl.SSLSocket.getpeercert(binary_form=False)` normally returns nested RDN tuples such as `((("commonName", "site"),),)`. With that shape, `_extract_peer_name()` returns `None`, so `/readiness` rejects valid mTLS callers. The receiver repeats the same shape assumption at [receiver.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/receiver.py:294).

   Recommendation: normalize both forms with a small shared helper, e.g. iterate each RDN and each attribute pair inside it. Add tests using the nested stdlib shape, not only the simplified mock shape.

3. **Readiness generation still depends on `client.enabled`, despite being a publisher responsibility.**

   The daemon now creates collector/normalizer for publisher mode at [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:75), but the loop that actually calls `publisher.update_readiness()` starts only when `self.config.client.enabled` is true at [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:143). If a site disables client mode because it does not want outgoing peer heartbeats, publisher mode can start and serve `/readiness` without ever producing readiness.

   Recommendation: split local collection/readiness publishing from outgoing peer heartbeat sending. `client.enabled` should control only `HeartbeatSender`, not the publisher update loop.

4. **The new controller reachability check can still report healthy on failed collection.**

   [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:298) treats `await self.collector.collect()` as proof that `slurmctld` is reachable. But [collector.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/collector.py:112) gathers sub-collectors with `return_exceptions=True`, and each sub-collector catches/logs its own failures at [collector.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/collector.py:139), [collector.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/collector.py:166), [collector.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/collector.py:191), and [collector.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/collector.py:219). So `collect()` usually returns an empty `ClusterMetrics` object instead of raising, and `_check_slurmctld_reachable()` returns `True`.

   Recommendation: have `collect()` expose collection health explicitly, or make reachability check a dedicated lightweight request that fails closed when the Slurm API/controller cannot be reached.

## High Findings

5. **Readiness documents are still not signed by the publisher.**

   README says the system produces signatures at [README.md](/home/samehuman/projects/slurmheartbeat/README.md:26), and `IMPLEMENTATION_SUMMARY.md` says readiness documents are signed at [IMPLEMENTATION_SUMMARY.md](/home/samehuman/projects/slurmheartbeat/IMPLEMENTATION_SUMMARY.md:92). [ReadinessMessage](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/protocol/schema.py:234) can sign, but [publisher.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/publisher.py:212) just returns `readiness.to_dict()`. Unless an external caller pre-signs the message before `update_readiness()`, `signature` remains `null`.

   Recommendation: either add explicit publisher signing config and sign before serving, or remove signed-readiness claims. mTLS alone may be enough for a first EFP readiness endpoint if documented honestly.

6. **Legacy P2P is still enabled by an unconfigured, default-true feature flag.**

   [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:102) checks `getattr(self.config.server, "enable_legacy_p2p", True)`, but `ServerConfig` has no such field in [config.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/config.py:65), and the example config has no such knob. In default `both` mode this means the legacy receiver still starts unless code is changed, not config. That keeps the project bigger than the EFP readiness-publisher contract.

   Recommendation: either add and parse an explicit `enable_legacy_p2p: false` default, or remove the legacy peer heartbeat path until EFP confirms push transport is required.

7. **Peer public keys are parsed into `client.federation` but never reach the receiver.**

   [config.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/config.py:262) loads top-level `federation.peer_public_keys` into `config.client.federation.peer_public_keys`. The receiver attempts to read `config.federation.peer_public_keys` at [receiver.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/server/receiver.py:245), but it receives `self.config.server` from [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:108). `ServerConfig` has no `federation` field, so receiver signature verification cannot be configured through the current YAML loader.

   Recommendation: put peer public keys where the receiver can actually read them, or pass a dedicated receiver/security config instead of `ServerConfig`.

8. **The heartbeat loop now polls Slurm twice per interval.**

   [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:188) collects metrics, then [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:193) calls `_check_slurmctld_reachable()`, which calls `collector.collect()` again at [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:300). That doubles Slurm REST traffic and can make readiness internally inconsistent if the two samples differ.

   Recommendation: make collection return both metrics and collection health in one pass, then derive readiness from that single observation.

9. **Maintenance state is hardcoded to an unconfigured local file and imports an undeclared direct dependency.**

   [main.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/main.py:312) checks `/var/run/slurm/heartbeat/maintenance` with `anyio.Path`, but neither the path nor behavior is configurable in `config.example.yaml`, and `anyio` is not listed as a direct dependency in [requirements.txt](/home/samehuman/projects/slurmheartbeat/requirements.txt:1) or [pyproject.toml](/home/samehuman/projects/slurmheartbeat/pyproject.toml:31). It may be installed transitively via `httpx`, but this code now imports it directly.

   Recommendation: either use `pathlib.Path.exists()` in an executor-free sync check or add a direct dependency and a documented `maintenance_file` config option.

10. **The collector still documents fallback sources that are not implemented.**

    [collector.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/collector.py:3) says OpenMetrics, `scontrol --json`, `sinfo/squeue`, and slurmrestd are supported. The implementation only uses slurmrestd-style HTTP calls via [collector.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/collector.py:95). `IMPLEMENTATION_SUMMARY.md` repeats the OpenMetrics/scontrol claim at [IMPLEMENTATION_SUMMARY.md](/home/samehuman/projects/slurmheartbeat/IMPLEMENTATION_SUMMARY.md:130).

    Recommendation: keep this project as a readiness adapter. Either implement those inputs deliberately, or document slurmrestd as the only current source and prefer native Slurm/OpenMetrics where sites already expose it.

11. **New status documents overstate readiness and duplicate audit content.**

    [IMPLEMENTATION_SUMMARY.md](/home/samehuman/projects/slurmheartbeat/IMPLEMENTATION_SUMMARY.md:7) and [FINAL_VERIFICATION_REPORT.md](/home/samehuman/projects/slurmheartbeat/FINAL_VERIFICATION_REPORT.md:4) both say `PRODUCTION READY`. The findings above contradict that. These files also duplicate the audit narrative and will likely drift again.

    Recommendation: keep one living recommendations/status file, or turn these into dated historical artifacts with conservative language.

## Medium Findings

12. **Tests pass but still miss the current failure modes.**

    The suite has useful regression tests for metrics text and publisher update state, but it does not catch the nested `peercert` shape, metrics initialization order, double metrics start, disabled-client publisher mode, peer public key wiring, or double Slurm collection. [tests/test_server.py](/home/samehuman/projects/slurmheartbeat/tests/test_server.py:147) uses the flattened `("commonName", "test-cluster")` subject shape that does not match the stdlib nested form.

    Recommendation: add small tests for the exact smoke probes in this audit before adding new features.

13. **Dead or near-dead configuration/documentation surface remains.**

    `config.example.yaml` still includes alerting, security, rate limiting, performance, compression, resource limits, and debug sections at [config.example.yaml](/home/samehuman/projects/slurmheartbeat/config.example.yaml:118), [config.example.yaml](/home/samehuman/projects/slurmheartbeat/config.example.yaml:148), [config.example.yaml](/home/samehuman/projects/slurmheartbeat/config.example.yaml:167), and [config.example.yaml](/home/samehuman/projects/slurmheartbeat/config.example.yaml:184). Most are not parsed or enforced by [config.py](/home/samehuman/projects/slurmheartbeat/slurmheartbeat/client/config.py:126).

    Recommendation: remove unimplemented active config fields. Keep aspirational behavior in ADRs, not in the example file users will deploy.

14. **Packaging and dependency cleanup is still needed.**

    [pyproject.toml](/home/samehuman/projects/slurmheartbeat/pyproject.toml:65) includes `slurmheartbeat = ["py.typed"]`, but no `slurmheartbeat/py.typed` file exists. [pyproject.toml](/home/samehuman/projects/slurmheartbeat/pyproject.toml:33) and [requirements.txt](/home/samehuman/projects/slurmheartbeat/requirements.txt:3) include `pydantic`, while the code uses dataclasses. `aiosmtplib` is listed in [requirements.txt](/home/samehuman/projects/slurmheartbeat/requirements.txt:24) and [pyproject.toml](/home/samehuman/projects/slurmheartbeat/pyproject.toml:48) without implemented email alerting.

    Recommendation: add `py.typed` or remove the package-data claim. Drop unused dependencies until corresponding code exists.

15. **Project metadata still has placeholders.**

    README clone/contact links still point to `your-org` and `your-email` at [README.md](/home/samehuman/projects/slurmheartbeat/README.md:53) and [README.md](/home/samehuman/projects/slurmheartbeat/README.md:301). Package URLs in [pyproject.toml](/home/samehuman/projects/slurmheartbeat/pyproject.toml:55), [CHANGELOG.md](/home/samehuman/projects/slurmheartbeat/CHANGELOG.md:109), and [systemd/slurm-heartbeat.service](/home/samehuman/projects/slurmheartbeat/systemd/slurm-heartbeat.service:3) also point to `your-org`.

    Recommendation: update metadata to the actual repository and support policy before publishing.

## Do Not Reinvent The Wheel

The useful product here is a narrow readiness contract: "Can this site safely receive federated work right now?" Keep the implementation small and boring.

- Use native Slurm federation state (`sacctmgr show federation`, `scontrol show federation`, FedState, cluster features) instead of building a parallel federation model.
- Use Slurm REST/OpenAPI/OpenMetrics where already deployed; avoid custom polling semantics that duplicate Slurm/Prometheus.
- Let Prometheus tooling own metrics exposition; avoid simultaneously running `start_http_server()` and an aiohttp `/metrics` route unless there is a clear deployment reason.
- Let site monitoring stacks own dashboards, alerting, history, and notifications.
- Treat the legacy peer heartbeat protocol as experimental until an EFP consumer explicitly requires push transport.

## Recommended Next Steps

1. Fix metrics construction order and single-start ownership.
2. Fix certificate subject parsing for the real nested `peercert` format in both publisher and receiver.
3. Decouple publisher readiness updates from `client.enabled`.
4. Replace the double-collection reachability check with explicit collection health.
5. Decide whether legacy P2P remains; if it does, wire `enable_legacy_p2p` and peer public keys through real config.
6. Either implement publisher signing for `ReadinessMessage` or stop claiming signed readiness.
7. Trim unimplemented config/docs/dependencies and remove duplicate "production ready" reports.
8. Add targeted tests for the smoke failures in this audit.

## References

- EuroHPC JU, "EuroHPC Federation Platform": https://www.eurohpc-ju.europa.eu/supercomputers/eurohpc-federation-platform_en
- EuroHPC JU, "First release of the EuroHPC Federation Platform", 2026-04-15: https://www.eurohpc-ju.europa.eu/first-release-eurohpc-federation-platform-streamline-access-europes-supercomputing-resources-2026-04-15_en
- SchedMD, "Slurm REST API": https://slurm.schedmd.com/rest.html
- SchedMD, "Slurm Federated Scheduling Guide": https://slurm.schedmd.com/federation.html
- SchedMD, "Slurm OpenAPI Plugins": https://slurm.schedmd.com/openapi.html
