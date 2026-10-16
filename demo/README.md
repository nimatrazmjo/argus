# Demo Workload — Sample Monitored App

> **Not part of the Argus platform.** This is a sample application that Argus
> *observes*, bundled only to generate realistic telemetry. Delete it and Argus
> is still a complete observability platform — it would just have no demo
> traffic to display until a real app sends it data.

Analogous to Datadog's own demo app (e.g. "Storedog"): a fake e-commerce mesh
whose sole purpose is to emit distributed traces, metrics, and logs so the
platform's service maps, APM views, alerting, and AIOps have live signal.

## What's here

| File | Purpose |
| :--- | :--- |
| `service_template.py` | Single-file Python 3.12 stdlib server; `SERVICE_ROLE` env switches behavior for all 10 roles. |
| `datadog-services.yaml` | K8s manifests (Service + Deployment) for the 10 services. |
| `apply-services.sh` | Staggered rollout into `argus-system` (throttles etcd write bursts, retries transient control-plane timeouts). |

## Topology

```
/api/checkout:  gateway → auth → catalog → order ─┬→ inventory
                                                  ├→ payment → billing
                                                  ├→ shipping
                                                  ├→ notification
                                                  └→ recommendation

/api/search:    gateway → catalog
                        → recommendation
```

| # | Service | Port | Role |
|---|---------|------|------|
| 1 | gateway | 8001 | Edge router / fan-out entry point |
| 2 | auth | 8002 | Token verify (leaf) |
| 3 | catalog | 8003 | Product listing (leaf) |
| 4 | order | 8004 | Orchestrator / saga hub |
| 5 | inventory | 8005 | Stock reserve (leaf) |
| 6 | payment | 8006 | Charge → billing |
| 7 | billing | 8007 | Invoice (leaf) |
| 8 | shipping | 8008 | Dispatch (leaf) |
| 9 | notification | 8009 | Notify (leaf) |
| 10 | recommendation | 8010 | Record events / suggest (leaf) |

Pass `trigger_error` in a request body/query to force downstream failures —
used to give alerting and AIOps real error signal.

## Run

```bash
./demo/apply-services.sh            # into the cluster (needs the platform + mirror)
# or run one service standalone:
SERVICE_ROLE=gateway PORT=8001 python3 demo/service_template.py
```
