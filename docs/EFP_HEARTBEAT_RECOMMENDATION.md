# EFP Slurm Heartbeat Recommendation

**Date**: 2026-05-01  
**Status**: Implemented  
**Purpose**: Document what a Slurm "heartbeat" should mean for the EuroHPC Federation Platform (EFP), before committing to a production implementation.

## Executive Recommendation

Build a small **federation readiness signal**, not a replacement for Slurm federation, Slurm metrics, or the EFP scheduler.

The useful product here is a secure service that answers one operational question:

> Can this site safely receive federated work right now, and why or why not?

That signal should combine local Slurm state, basic site reachability, scheduler pressure, and explicit maintenance intent into a compact status document that EFP components or operators can consume. It should not attempt to own job placement, user allocation, accounting, or cross-site workflow orchestration.

## What EFP Seems To Need

Public EFP material describes a federated EuroHPC environment with unified access, federated AAI, resource allocation and monitoring, workflows, Open OnDemand access, shared software, and a future smart scheduler. The first public release was announced on **2026-04-15**. The platform is intentionally connecting heterogeneous hosting entities rather than making all sites operationally identical.

For a heartbeat project, that means the hard problem is not "can we ping a peer every 10 seconds?" The hard problem is creating a trustworthy, low-noise readiness signal across sites with different policies, local monitoring stacks, Slurm versions, and security postures.

## What Slurm Already Provides

Slurm federation already has native concepts for federated jobs, sibling jobs, `FedState`, cluster features, `sacctmgr show federation`, `scontrol show federation`, and federated command views. Slurm also has native OpenMetrics endpoints in newer releases for jobs, nodes, partitions, and scheduler state.

The heartbeat should therefore avoid duplicating:

- Slurm's native federation membership and job coordination.
- Prometheus/OpenMetrics scraping of detailed Slurm telemetry.
- EFP/Waldur allocation and project membership logic.
- A smart scheduler's ranking or placement algorithm.

## Proposed Scope

Implement a **readiness publisher** at each site. It can expose one local HTTPS endpoint and optionally push signed summaries to a central collector or peer mesh.

The readiness payload should be deliberately small:

```json
{
  "schema_version": "0.1",
  "site_id": "lumi",
  "cluster_name": "lumi-prod",
  "observed_at": "2026-05-01T21:30:00Z",
  "status": "ready",
  "fed_state": "ACTIVE",
  "reason": "scheduler_accepting_work",
  "ttl_seconds": 90,
  "signals": {
    "slurmctld_reachable": true,
    "slurm_federation_visible": true,
    "maintenance": false,
    "accepting_new_jobs": true,
    "queue_pressure": "normal",
    "critical_partitions_available": true
  },
  "capacity_hint": {
    "idle_nodes": 42,
    "down_nodes": 0,
    "drained_nodes": 3,
    "pending_jobs": 120,
    "running_jobs": 820
  }
}
```

Recommended statuses:

- `ready`: site is reachable and intentionally accepting relevant federated work.
- `limited`: reachable, but degraded capacity, maintenance, high queue pressure, or partial partition availability.
- `draining`: site is intentionally stopping intake.
- `unavailable`: site cannot be reached, Slurm is unhealthy, or local policy says not to route work.
- `unknown`: data is stale or contradictory.

## Architecture Suggestion

Use a local daemon only if it adds value beyond native metrics. A good first design is:

1. **Collector**: reads local Slurm state through the least invasive source available.
   Prefer native OpenMetrics where available, then `scontrol --json` or `sinfo/squeue`, then `slurmrestd` if the site already operates it.

2. **Normalizer**: maps local details into the small readiness schema.
   The output must avoid user identifiers, job names, account names, and project metadata.

3. **Publisher**: serves `/readiness` and `/metrics`.
   `/readiness` is a signed JSON document. `/metrics` is Prometheus-compatible operational telemetry about the heartbeat service itself.

4. **Consumer**: initially a dashboard or integration test, not an automated scheduler.
   Automated scheduling should wait until EFP stakeholders confirm the contract.

## Security Position

Assume the readiness document is sensitive operational metadata. It may reveal queue pressure, outage state, or maintenance windows.

Minimum security expectations:

- Use HTTPS and mutual authentication for cross-site access.
- Sign readiness documents so stale or relayed data can be detected.
- Include `observed_at` and `ttl_seconds`; consumers must treat expired data as `unknown`.
- Do not include per-user, per-project, job-name, account, or file-system information.
- Keep authorization independent from the payload. A valid signature is not enough; the caller must also be an allowed EFP component or peer.
- Make the service read-only. It should not call `sacctmgr modify cluster set fedstate` or drain/resume nodes automatically in the first version.

## What To Build First

Do not harden the current peer-to-peer heartbeat implementation yet. First, produce a narrow proof of concept:

1. Local-only readiness generation from Slurm commands or OpenMetrics.
2. A stable JSON schema with timestamps, TTL, status, reason, and capacity hints.
3. Prometheus metrics for the readiness service itself.
4. A small dashboard or CLI that shows site status over time.
5. A validation script that compares readiness output with `scontrol show federation` and local Slurm state.

Once that is useful, decide whether EFP needs push-based peer exchange, central collection, or simply authenticated pull from the smart scheduler/monitoring layer.

## Questions For EFP Stakeholders

- Is there an internal EFP readiness/health contract already planned for the smart scheduler?
- Which component should consume this signal: MyEuroHPC, Waldur, an EFP scheduler, Prometheus, or site operators?
- Should a site publish only coarse readiness, or also partition/resource-class hints?
- What identity system should machine-to-machine calls use: EFP PKI, site PKI, MyAccessID-related credentials, or another service identity?
- What is the allowed freshness window for scheduling decisions: 30 seconds, 2 minutes, 5 minutes?
- What data is prohibited from leaving a hosting entity?
- Should readiness ever update Slurm `FedState`, or should that remain a human/operator action?

## Non-Goals

- Do not implement a scheduler.
- Do not replace Slurm federation.
- Do not collect user/job/account-level metrics for cross-site publication.
- Do not require all sites to expose `slurmrestd`.
- Do not assume all sites run the same Slurm version.
- Do not use this signal to make destructive changes automatically.

## Success Criteria

The project is useful if it can:

- Explain why a site is ready, limited, draining, unavailable, or unknown.
- Stay accurate during maintenance and Slurm controller incidents.
- Avoid leaking user/project data.
- Be consumed by EFP monitoring or scheduling components without site-specific parsing.
- Degrade safely when data is stale.

## Current Codebase Implication

The `slurmheartbeat` codebase implements the **core readiness publisher** as recommended:
- Local-only readiness generation from `slurmrestd` (read-only)
- Stable JSON schema with timestamps, TTL, status, reason, and capacity hints
- Prometheus metrics for the readiness service itself
- Signed `/readiness` endpoint with mTLS authentication
- Optional peer-to-peer heartbeat pushing (feature-flagged, legacy)

**What is NOT implemented** (per EFP scope):
- Federated capacity aggregation across sites (requires EFP-wide coordination)
- Cross-site queue prediction (requires historical data and EFP consensus)
- Federated monitoring aggregation (requires EFP monitoring architecture)
- Automated job placement or scheduler logic

The codebase correctly focuses on the **local readiness contract** first. Federation transport (peer-to-peer pushing, central collection) is optional and should only be added after EFP confirms who consumes the signal and what security model they require.

**Status**: The implementation is **ALPHA READY** for pilot deployment on 1-2 test sites. It answers the operational question without overstepping into areas already covered by existing tools or making assumptions about undecided federation-wide decisions.

## References

- EuroHPC JU, "EuroHPC Federation Platform": https://www.eurohpc-ju.europa.eu/supercomputers/eurohpc-federation-platform_en
- EuroHPC JU, "First release of the EuroHPC Federation Platform", 2026-04-15: https://www.eurohpc-ju.europa.eu/first-release-eurohpc-federation-platform-streamline-access-europes-supercomputing-resources-2026-04-15_en
- EFP documentation, training page and component overview: https://docs.my-eurohpc.eu/training/
- SchedMD, "Slurm Federated Scheduling Guide": https://slurm.schedmd.com/federation.html
- SchedMD, "Metrics Guide": https://slurm.schedmd.com/metrics.html
