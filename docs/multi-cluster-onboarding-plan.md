# Multi-Cluster Onboarding Plan — DEV / STAGING / PROD

Bring `DHS-DEV`, `DHS-STAGING`, and `DHS-PROD` AKS clusters onto one Argus hub.

## Locked decisions

- **Hub** lives in the existing non-prod (shared-services) resource group: ClickHouse HA, SigNoz, MinIO, ingest gateway, alerting, SLO, paging, SSO, AIOps.
- **Spokes** (DEV / STAGING / PROD) run an agent bundle only and **push** OTLP to the hub. No inbound access to the clusters; the hub holds no cluster credentials.
- **Redaction happens spoke-side**, before telemetry leaves each cluster. Hub re-redacts as defense in depth.
- **Isolation** is by `tenant_id` (stamped per cluster) enforced by the existing ClickHouse row policies.
- Hub RG carries **prod-grade RBAC** regardless of its "non-prod" label, because PROD telemetry lands there.

## What changes vs. what already works

Already edge-side in `charts/argus/templates/otel.yaml`: the spoke gateway does `k8sattributes` enrichment and `transform/redaction`. We keep those on the spoke and only change where the gateway ships and what it stamps.

| # | Change | File(s) |
|---|--------|---------|
| 1 | `mode: hub \| agent` toggle; agent disables backend components | `charts/argus/values.yaml`, `templates/*.yaml` guards |
| 2 | Gateway exporter configurable → hub endpoint in agent mode | `templates/otel.yaml` |
| 3 | `resource` processor stamping `deployment.environment`, `k8s.cluster.name`, `tenant_id` | `templates/otel.yaml` |
| 4 | Hub ingest gateway: internal LB + TLS + bearer-token auth, drop `k8sattributes` | `templates/otel.yaml`, `templates/ingress.yaml` |
| 5 | Per-cluster helmfile environments | `helmfile.yaml` |

---

## Phase 0 — Prereqs & network

**Goal:** hub reachable from one spoke, nothing deployed yet.

- Confirm hub ingest will be exposed on an Azure internal LB (`service.beta.kubernetes.io/azure-load-balancer-internal: "true"`).
- VNet-peer the hub VNet to the DEV VNet. NSG on the hub ingest subnet admits only the DEV node subnet on 4317/4318.
- Each spoke can resolve its own image registry/ACR (`ARGUS_IMAGE_REGISTRY`).

**Small test** — from a throwaway pod in the DEV cluster, confirm L4 reachability to the (planned) hub ILB IP:
```bash
kubectl -n default run netcheck --rm -it --image=busybox --restart=Never -- \
  sh -c 'nc -zvw3 <HUB_ILB_IP> 4317 && echo REACHABLE'
```
Pass = `REACHABLE`. If it hangs, fix peering/NSG before going further.

---

## Phase 1 — Chart split (hub / agent modes)

**Goal:** `helm template` produces the right resource set for each mode. No cluster changes.

- Add `mode: hub` (default) to `values.yaml`. Guard `clickhouse.yaml`, `signoz.yaml`, `storage.yaml`, `alerting.yaml`, `slo` bits, `paging.yaml`, `sso.yaml`, `aiops.yaml`, `correlation.yaml`, `rum.yaml`, `demo.yaml` with `{{- if eq .Values.mode "hub" }}`.
- Agent mode keeps only `otel.yaml`, `beyla.yaml`, `infra-metrics.yaml`.
- Add values: `hub.endpoint`, `hub.tls.enabled`, `hub.auth.token`, `cluster.name`, `environment`, `tenant.id`.

**Small test** — render-only, no apply:
```bash
helm template argus ./charts/argus --set mode=agent \
  | grep -E 'kind: (ClickHouseInstallation|StatefulSet)' && echo "FAIL: backend leaked into agent" || echo "PASS: agent has no backend"

helm template argus ./charts/argus --set mode=hub \
  | grep -q 'clickhouse' && echo "PASS: hub has backend"
```

---

## Phase 2 — Identity stamping

**Goal:** every record carries env / cluster / tenant so the hub can tell DEV from PROD.

- Add a `resource` processor to the spoke gateway (first in each pipeline):
  ```yaml
  resource/identity:
    attributes:
      - { key: deployment.environment, value: "{{ .Values.environment }}", action: upsert }
      - { key: k8s.cluster.name,       value: "{{ .Values.cluster.name }}", action: upsert }
      - { key: tenant_id,              value: "{{ .Values.tenant.id }}",   action: upsert }
  ```
- Note: the existing `tenant-policies.sql` row policies filter on `ResourceAttributes['tenant_id']` that **nothing currently sets** — this is the step that makes tenancy real.

**Small test** — run the collector config locally against a sample span and assert the attribute is present (no cluster needed):
```bash
# send one OTLP span through a local collector built from the rendered agent config,
# then query the debug exporter / file exporter output:
grep -q '"tenant_id":"dev"' /tmp/otel-out.json && echo PASS || echo FAIL
```

---

## Phase 3 — Hub ingest hardening

**Goal:** the hub only accepts authenticated OTLP and never mis-enriches remote pods.

- Dedicated ingest `OpenTelemetryCollector` service as internal LB.
- Add `bearertokenauth` extension on the OTLP receiver; TLS on 4317/4318.
- **Remove `k8sattributes`** from the hub ingest pipeline (it cannot resolve remote-cluster pod IPs). Keep `transform/redaction` as defense in depth; keep the ClickHouse + SigNoz exporters.

**Small test** — token enforcement, from the hub cluster:
```bash
# no token -> rejected
grpcurl -plaintext -d '{}' <HUB_ILB_IP>:4317 \
  opentelemetry.proto.collector.trace.v1.TraceService/Export 2>&1 | grep -qi 'unauth' && echo "PASS: rejects no-token"
# with token -> accepted (expect no auth error)
grpcurl -H "authorization: Bearer $ARGUS_SPOKE_TOKEN" -plaintext -d '{"resourceSpans":[]}' \
  <HUB_ILB_IP>:4317 opentelemetry.proto.collector.trace.v1.TraceService/Export && echo "PASS: accepts token"
```

---

## Phase 4 — Tenancy enforcement

**Goal:** a DEV identity cannot read PROD rows.

- Apply tenant users (`tenant_dev`, `tenant_staging`, `tenant_prod`) and ensure `tenant-policies.sql` row policies cover `otel_traces`, `otel_logs`, `otel_metrics_*` for those users.

**Small test** — against hub ClickHouse, after Phase 5 has some prod data flowing:
```sql
-- as tenant_dev
SELECT count() FROM default.otel_traces WHERE ResourceAttributes['tenant_id']='prod';
-- expect 0 rows returned for tenant_dev; non-zero only for 'default' admin
```

---

## Phase 5 — DEV pilot (first real spoke)

**Goal:** real DEV telemetry in SigNoz, tagged `environment=dev`, redacted, isolated.

- Install OTel operator + `argus` chart in agent mode on DEV:
  ```bash
  helm install argus ./charts/argus -n argus-system --create-namespace \
    --set mode=agent --set environment=dev --set cluster.name=dhs-dev \
    --set tenant.id=dev --set hub.endpoint=<HUB_ILB_IP>:4317 \
    --set hub.auth.token=$ARGUS_DEV_TOKEN
  ```
- Annotate one DEV namespace for auto-instrumentation.

**Small test** — end-to-end + redaction proof:
```bash
# 1. hit an instrumented DEV endpoint that logs a fake SSN
curl -s https://<dev-app>/healthz?ssn=123-45-6789 >/dev/null
# 2. in SigNoz, filter traces by deployment.environment=dev -> the request appears
# 3. in hub ClickHouse, confirm the SSN was scrubbed at the spoke:
clickhouse-client --query "SELECT count() FROM default.otel_logs \
  WHERE Body LIKE '%123-45-6789%'"   # expect 0
```
Pass = trace visible under `env=dev` AND zero un-redacted SSN hits.

---

## Phase 6 — STAGING, then PROD

**Goal:** repeat Phase 5 per environment; PROD last, under change control.

- Identical install, changing `environment` / `cluster.name` / `tenant.id` / token.
- PROD: schedule a window, pre-stage the ILB/peering, deploy agent, watch spoke gateway memory for the first hour (Beyla + redaction are the hot paths).

**Small test (per env)** — same E2E as Phase 5, plus confirm cross-env separation in SigNoz:
```
Filter by deployment.environment=staging  -> only staging services
Filter by deployment.environment=prod     -> only prod services
```

---

## Phase 7 — Ops wiring

**Goal:** alerting, SLOs, paging, and SSO scoped per environment.

- Scope alert rules / SLOs by `deployment.environment` so a DEV blip doesn't page the PROD on-call.
- Map SSO groups → tenant users (`dhs-dev-eng` → `tenant_dev`, etc.).

**Small test** — log into SigNoz as a DEV-group user; attempt to open a PROD service view; expect empty/denied. Fire a synthetic DEV alert; confirm it routes to the DEV channel, not PROD paging.

---

## Rollback

Each spoke is independent. To remove one: `helm uninstall argus -n argus-system` on that cluster. The hub and other spokes are unaffected; no data is deleted (it ages out via the 72h TTL / tiering).
