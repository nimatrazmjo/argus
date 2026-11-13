# Argus — Azure AKS Deployment Guide

Step-by-step install of Argus on Azure: AKS, ACR, Key Vault, Managed Disks (hot
storage) and Blob Storage (cold storage). Follow sections in order.

---

## Table of Contents

1. [Where logs, traces and metrics are stored](#1-where-logs-traces-and-metrics-are-stored)
2. [Prerequisites](#2-prerequisites)
3. [Variables & Resource Group](#3-variables--resource-group)
4. [Capacity sizing](#4-capacity-sizing)
5. [AKS cluster](#5-aks-cluster)
6. [Azure Container Registry (ACR)](#6-azure-container-registry-acr)
7. [Mirror images into ACR](#7-mirror-images-into-acr)
8. [Key Vault — secrets](#8-key-vault--secrets)
9. [Hot tier — Azure Managed Disk StorageClass](#9-hot-tier--azure-managed-disk-storageclass)
10. [Cold tier — Azure Blob Storage + Workload Identity](#10-cold-tier--azure-blob-storage--workload-identity)
11. [Wire storage into ClickHouse](#11-wire-storage-into-clickhouse)
12. [Connect kubectl](#12-connect-kubectl)
13. [Deploy operators (Phase 1)](#13-deploy-operators-phase-1)
14. [Deploy Argus workloads (Phase 2)](#14-deploy-argus-workloads-phase-2)
15. [Apply retention, tenancy & SSO](#15-apply-retention-tenancy--sso)
16. [Access the UI](#16-access-the-ui)
17. [Verify the platform](#17-verify-the-platform)
18. [Backups](#18-backups)
19. [Multi-environment (DEV / STAGING / PROD)](#19-multi-environment-dev--staging--prod)
20. [Production hardening checklist](#20-production-hardening-checklist)
21. [Troubleshooting](#21-troubleshooting)
22. [Implementation checklist (repo changes, phased)](#22-implementation-checklist-repo-changes-phased)

---

## 1. Where logs, traces and metrics are stored

All three signals go to **one place: ClickHouse**, via the OTel collectors.
SigNoz is only the UI/query layer.

```
apps ─OTLP─► OTel agent/gateway ─► signoz-otel-collector ─► ClickHouse
                                                              │
                          ┌───────────────────────────────────┤
                          ▼                                   ▼
                HOT tier (days)                      COLD tier (weeks–months)
        Azure Managed Disk PVC (Premium SSD)     Azure Blob Storage container
        local ClickHouse volume `hot`            ClickHouse disk `azure_cold`
                                                              │
                                                              ▼
                                                  TTL DROP (retention end)
```

| Signal  | Tables (ClickHouse)                          | Hot            | Cold (Blob)    | Dropped        |
|---------|----------------------------------------------|----------------|----------------|----------------|
| Logs    | `default.otel_logs`                          | 0–7 d          | 7–30 d         | > 30 d         |
| Traces  | `default.otel_traces`                        | 0–7 d          | 7–30 d         | > 30 d         |
| Metrics (raw)   | `default.otel_metrics_*`             | 0–7 d          | 7–30 d         | > 30 d         |
| Metrics 1m rollup | `signoz_metrics.samples_1m`        | 0–30 d         | 30–90 d        | > 90 d         |
| Metrics 1h rollup | `signoz_metrics.samples_1h`        | 0–90 d         | 90–365 d       | > 365 d        |

Day counts are defaults — set yours in section 4 / 15.

**Do not store telemetry in:** pod ephemeral disk (lost on reschedule), Azure
Files/NFS (too slow, bad locking for ClickHouse), or Blob as the *only* tier
(too slow for recent data).

### Span coverage & sampling

Current behavior (repo defaults):
- **Head sampling:** `deploy/otel/instrumentation.yaml` uses `parentbased_always_on` → 100% of spans from auto-instrumented apps (Python, Node.js, Java). No tail sampling in the gateway.
- **Traces pipeline** (`deploy/otel/gateway.yaml`): `memory_limiter → k8sattributes → transform/redaction → transform/cardinality → batch`. Nothing drops spans.
- **Logs:** `filter/log_level` drops DEBUG/TRACE unless the service sets `allow_debug`.
- **Non-instrumented languages:** covered only by Beyla (eBPF), HTTP/gRPC spans, less detail.

Where spans can still be lost:

| Cause | Mitigation |
|---|---|
| Gateway `memory_limiter` (400 MiB) refuses data in bursts | Raise limits / replicas; add `sending_queue` + `retry_on_failure` on exporter |
| ClickHouse down or hot disk full | Alert on disk > 70%, persistent queue (`file_storage`) on gateway |
| Context not propagated (no `traceparent`) | Orphan/fragmented traces; fix in the service or use Beyla |
| `transform/cardinality` trims attributes | Spans kept, attributes reduced; review rules |
| TTL retention | Spans deleted after TTL (§1) |

Storage impact: 100% span retention is the largest driver of hot-disk size (§4).
At high volume, add **tail sampling** in the gateway (needs a loadbalancing
exporter or a single gateway replica so all spans of a trace hit one pod):

```yaml
processors:
  tail_sampling:
    decision_wait: 10s
    num_traces: 50000
    policies:
      - name: errors
        type: status_code
        status_code: { status_codes: [ERROR] }
      - name: slow
        type: latency
        latency: { threshold_ms: 1000 }
      - name: baseline
        type: probabilistic
        probabilistic: { sampling_percentage: 10 }
# traces pipeline: [memory_limiter, k8sattributes, tail_sampling, transform/redaction, transform/cardinality, batch]
```

Keeps 100% of errors and slow traces plus 10% of the rest. Span-derived RED
metrics must be computed **before** sampling (the SigNoz collector's
`signozspanmetrics` runs after the gateway, so sampled-out spans would skew
them — compute metrics in the gateway with the `spanmetrics` connector first).

---

## 2. Prerequisites

```bash
brew install azure-cli kubectl helm helmfile jq
az version              # >= 2.60
helm version            # >= 3.14
helm plugin install https://github.com/databus23/helm-diff   # helmfile needs it
```

```bash
az login
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"
az provider register --namespace Microsoft.ContainerService
az provider register --namespace Microsoft.Storage
az provider register --namespace Microsoft.KeyVault
az provider register --namespace Microsoft.ContainerRegistry
```

You need `Owner` (or `Contributor` + `User Access Administrator`) on the
subscription/resource group — role assignments in section 10 require it.

---

## 3. Variables & Resource Group

Set once per shell. Re-export these whenever you open a new terminal.

```bash
export ENV="prod"                              # dev | staging | prod
export RG="argus-${ENV}-rg"
export LOCATION="eastus"
export CLUSTER_NAME="argus-${ENV}-aks"
export ACR_NAME="argusacr${ENV}"               # globally unique, lowercase, no dashes
export KV_NAME="argus-${ENV}-kv"               # globally unique, 3-24 chars
export STORAGE_ACCOUNT="argusstore${ENV}"      # globally unique, lowercase, 3-24 chars
export STORAGE_CONTAINER="clickhouse-cold"
export NAMESPACE="argus-system"
export UAMI_NAME="argus-clickhouse-identity"   # managed identity for Blob access

az group create --name "$RG" --location "$LOCATION"
```

---

## 4. Capacity sizing

Decide before creating disks.

```
hot_disk_GB = daily_ingest_GB × hot_days × 1.2     # compression + merge headroom
```

Keep disk usage under ~70%. Example: 50 GB/day × 7 d × 1.2 ≈ 420 GB → provision
512 GB–1 TB.

| Env     | ClickHouse hot PVC | Keeper PVC | Blob cold   | Node pool            |
|---------|--------------------|------------|-------------|----------------------|
| DEV     | 50–100 Gi          | 5 Gi       | optional    | 3 × Standard_D4s_v5  |
| STAGING | 200 Gi             | 10 Gi      | 1 container | 3 × Standard_D4s_v5  |
| PROD    | from formula (≥512 Gi) | 10–20 Gi | 1 container | 3 × Standard_D8s_v5 |

Rule of thumb: **under ~500 GB total, skip Blob** and size the hot disk for the
entire retention window (simpler). Use Blob tiering for longer retention / larger
volume. Note: the repo currently ships `2Gi` PVCs — demo size only; always
override for Azure (section 11).

---

## 5. AKS cluster

Workload Identity and the OIDC issuer are **required** (cold tier auth, section 10).
Use zones so ZRS disks can reattach after a zone failure.

```bash
az aks create \
  --resource-group "$RG" \
  --name "$CLUSTER_NAME" \
  --location "$LOCATION" \
  --node-count 3 \
  --node-vm-size Standard_D8s_v5 \
  --zones 1 2 3 \
  --network-plugin azure \
  --enable-oidc-issuer \
  --enable-workload-identity \
  --enable-managed-identity \
  --generate-ssh-keys

az aks show -g "$RG" -n "$CLUSTER_NAME" --query provisioningState -o tsv   # Succeeded
```

Notes:
- DEV can use `Standard_D4s_v5` and no `--zones`.
- ClickHouse is memory-heavy: prefer ≥ 32 GB nodes in PROD.
- Already have a cluster? Enable the features instead:
  `az aks update -g "$RG" -n "$CLUSTER_NAME" --enable-oidc-issuer --enable-workload-identity`

---

## 6. Azure Container Registry (ACR)

```bash
az acr create -g "$RG" -n "$ACR_NAME" --sku Standard

# let AKS nodes pull from ACR without secrets
az aks update -g "$RG" -n "$CLUSTER_NAME" --attach-acr "$ACR_NAME"

export ACR_LOGIN_SERVER=$(az acr show -n "$ACR_NAME" --query loginServer -o tsv)
echo "$ACR_LOGIN_SERVER"      # e.g. argusacrprod.azurecr.io
```

---

## 7. Mirror images into ACR

Argus runs from a fixed image list (`deploy/mirror/images.txt`). Import all of it:

```bash
while IFS= read -r line; do
  [[ -z "$line" || "$line" == \#* ]] && continue
  [[ "$line" == localhost:* ]] && continue
  dest=$(echo "$line" | sed 's|.*/||')
  echo "Importing $line -> $ACR_LOGIN_SERVER/argus/$dest"
  az acr import -n "$ACR_NAME" --source "$line" --image "argus/$dest" --force
done < deploy/mirror/images.txt
```

`az acr import` pulls server-side; no local Docker needed. Images built in-repo
(e.g. `sample-service`, `aiops`) must be built and pushed with `az acr build`:

```bash
az acr build -r "$ACR_NAME" -t argus/sample-service:1.0.0 deploy/sample-app
```

Verify: `az acr repository list -n "$ACR_NAME" -o table`

---

## 8. Key Vault — secrets

```bash
az keyvault create -n "$KV_NAME" -g "$RG" -l "$LOCATION" --enable-rbac-authorization true

# grant yourself write access
az role assignment create \
  --assignee "$(az ad signed-in-user show --query id -o tsv)" \
  --role "Key Vault Secrets Officer" \
  --scope "$(az keyvault show -n "$KV_NAME" --query id -o tsv)"
```

Generate **random** secrets — never use the repo defaults on Azure:

```bash
for s in clickhouse-password jwt-secret rum-ingest-token paging-webhook-token \
         synthetic-bearer-token signoz-admin-password idp-center-password; do
  az keyvault secret set --vault-name "$KV_NAME" --name "$s" \
    --value "$(openssl rand -hex 24)" -o none
done
```

Pull into env vars for the next steps:

```bash
kvget() { az keyvault secret show --vault-name "$KV_NAME" --name "$1" --query value -o tsv; }
export CLICKHOUSE_PASSWORD=$(kvget clickhouse-password)
export JWT_SECRET=$(kvget jwt-secret)
export RUM_INGEST_TOKEN=$(kvget rum-ingest-token)
export PAGING_WEBHOOK_TOKEN=$(kvget paging-webhook-token)
export SYNTHETIC_BEARER_TOKEN=$(kvget synthetic-bearer-token)
```

---

## 9. Hot tier — Azure Managed Disk StorageClass

ClickHouse hot data lives on a **Managed Disk PVC per ClickHouse pod**
(block storage, ReadWriteOnce).

Create `deploy/azure/storageclass-premium.yaml`:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: argus-premium
provisioner: disk.csi.azure.com
parameters:
  skuName: Premium_ZRS          # use Premium_LRS if node pool is NOT zonal
  cachingMode: ReadOnly
reclaimPolicy: Retain           # keep disk if PVC is deleted
allowVolumeExpansion: true
volumeBindingMode: WaitForFirstConsumer
```

```bash
mkdir -p deploy/azure
kubectl apply -f deploy/azure/storageclass-premium.yaml
kubectl get storageclass argus-premium
```

Options:
- Heavy ingest / need tuned IOPS: `skuName: PremiumV2_LRS` (zonal pool required) or `UltraSSD_LRS`.
- Never use `azurefile` / NFS for ClickHouse.
- Expand later without downtime: `kubectl patch pvc <name> -p '{"spec":{"resources":{"requests":{"storage":"1Ti"}}}}'`

---

## 10. Cold tier — Azure Blob Storage + Workload Identity

> Azure Blob is **not** S3-compatible. Use ClickHouse's native
> `azure_blob_storage` disk (not the `s3` disk type). The repo default
> (SeaweedFS `argus-s3`) is for air-gapped/local clusters only — on Azure, drop it.

### 10.1 Storage account + container

```bash
az storage account create \
  -n "$STORAGE_ACCOUNT" -g "$RG" -l "$LOCATION" \
  --sku Standard_ZRS --kind StorageV2 \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false

az storage container create \
  --account-name "$STORAGE_ACCOUNT" -n "$STORAGE_CONTAINER" --auth-mode login
```

### 10.2 Managed identity (no keys)

```bash
az identity create -g "$RG" -n "$UAMI_NAME" -l "$LOCATION"

export UAMI_CLIENT_ID=$(az identity show -g "$RG" -n "$UAMI_NAME" --query clientId -o tsv)
export UAMI_PRINCIPAL_ID=$(az identity show -g "$RG" -n "$UAMI_NAME" --query principalId -o tsv)

# data-plane access to this storage account only
az role assignment create \
  --assignee-object-id "$UAMI_PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Storage Blob Data Contributor" \
  --scope "$(az storage account show -n "$STORAGE_ACCOUNT" -g "$RG" --query id -o tsv)"
```

### 10.3 Federate the identity with the ClickHouse ServiceAccount

```bash
export OIDC_ISSUER=$(az aks show -g "$RG" -n "$CLUSTER_NAME" --query oidcIssuerProfile.issuerUrl -o tsv)

az identity federated-credential create \
  --name argus-clickhouse-fic \
  --identity-name "$UAMI_NAME" -g "$RG" \
  --issuer "$OIDC_ISSUER" \
  --subject "system:serviceaccount:${NAMESPACE}:clickhouse" \
  --audience api://AzureADTokenExchange
```

The ServiceAccount name (`clickhouse`) must match section 11.

### 10.4 Lifecycle & safety (optional)

- Do **not** add a Blob lifecycle delete rule on this container — ClickHouse owns
  the objects (TTL deletes them). A lifecycle rule would corrupt live parts.
- Enable soft delete: `az storage account blob-service-properties update -n "$STORAGE_ACCOUNT" -g "$RG" --enable-delete-retention true --delete-retention-days 7`

### 10.5 Fallback: connection string (not recommended)

If Workload Identity is not possible:

```bash
export STORAGE_CONN=$(az storage account show-connection-string -n "$STORAGE_ACCOUNT" -g "$RG" -o tsv)
az keyvault secret set --vault-name "$KV_NAME" --name storage-connection-string --value "$STORAGE_CONN" -o none
kubectl -n "$NAMESPACE" create secret generic argus-blob-secret \
  --from-literal=AZURE_STORAGE_CONNECTION_STRING="$STORAGE_CONN"
```

and use `<connection_string from_env="AZURE_STORAGE_CONNECTION_STRING"/>` in the
disk definition below instead of `use_workload_identity`.

---

## 11. Wire storage into ClickHouse

The repo ships a demo config (SeaweedFS cold disk, 2Gi default-class PVC). Edit
**`charts/argus/templates/clickhouse.yaml`** (the same blocks exist in
`deploy/clickhouse/clickhouse-ha.yaml` for non-Helm installs).

### 11.1 ServiceAccount with Workload Identity

Add to the chart (new template `charts/argus/templates/clickhouse-sa.yaml`):

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: clickhouse
  namespace: {{ .Release.Namespace }}
  annotations:
    azure.workload.identity/client-id: "{{ .Values.azure.clickhouseIdentityClientId }}"
```

In the ClickHouse `podTemplate`, add:

```yaml
metadata:
  labels:
    azure.workload.identity/use: "true"
spec:
  serviceAccountName: clickhouse
```

### 11.2 Replace the cold disk in `storage.xml`

Replace the `s3_cold` disk and policy with:

```xml
<clickhouse>
  <storage_configuration>
    <disks>
      <azure_cold>
        <type>object_storage</type>
        <object_storage_type>azure_blob_storage</object_storage_type>
        <metadata_type>local</metadata_type>
        <storage_account_url>https://{{ .Values.azure.storageAccount }}.blob.core.windows.net</storage_account_url>
        <container_name>{{ .Values.azure.storageContainer }}</container_name>
        <use_workload_identity>true</use_workload_identity>
      </azure_cold>
    </disks>
    <policies>
      <tiered_hot_cold>
        <volumes>
          <hot><disk>default</disk></hot>
          <cold>
            <disk>azure_cold</disk>
            <prefer_not_to_merge>true</prefer_not_to_merge>
          </cold>
        </volumes>
        <move_factor>0.1</move_factor>
      </tiered_hot_cold>
    </policies>
  </storage_configuration>
</clickhouse>
```

The policy name `tiered_hot_cold` is unchanged, so all existing TTL/`storage_policy`
statements in `deploy/clickhouse/retention-policies.sql` and `otel-schema.sql`
keep working. `move_factor` 0.1 also spills to cold if hot disk gets > 90% full.

### 11.3 Hot PVC size + StorageClass

Replace the `volumeClaimTemplates` blocks:

```yaml
# ClickHouse data (hot)
volumeClaimTemplates:
  - name: data-storage
    spec:
      accessModes: [ReadWriteOnce]
      storageClassName: argus-premium
      resources:
        requests:
          storage: {{ .Values.clickhouse.hotStorage }}   # e.g. 512Gi
# Keeper
  - name: keeper-storage
    spec:
      accessModes: [ReadWriteOnce]
      storageClassName: argus-premium
      resources:
        requests:
          storage: {{ .Values.clickhouse.keeperStorage }} # e.g. 10Gi
```

Note: `volumeClaimTemplates` of an existing StatefulSet are immutable. On a fresh
install this is fine; on an upgrade delete the CHI/PVCs first (data loss) or
expand the PVC in place (section 9).

### 11.4 Azure values file

Create `charts/argus/values-azure.yaml`:

```yaml
imageRegistry: argusacrprod.azurecr.io      # your $ACR_LOGIN_SERVER

azure:
  storageAccount: argusstoreprod            # $STORAGE_ACCOUNT
  storageContainer: clickhouse-cold         # $STORAGE_CONTAINER
  clickhouseIdentityClientId: "<UAMI_CLIENT_ID>"   # echo $UAMI_CLIENT_ID

clickhouse:
  hotStorage: 512Gi
  keeperStorage: 10Gi

# SeaweedFS cold store is for air-gapped clusters only — disable on Azure
storage:
  s3Enabled: false
```

> If `storage.s3Enabled` does not yet exist in the chart, wrap
> `charts/argus/templates/storage.yaml` in `{{- if .Values.storage.s3Enabled | default true }} … {{- end }}`.

Add the file to `helmfile.yaml` under the `argus` release `values:` list, after
`charts/argus/values.yaml`.

---

## 12. Connect kubectl

```bash
az aks get-credentials -g "$RG" -n "$CLUSTER_NAME" --overwrite-existing
kubectl get nodes                                  # 3 Ready
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
```

---

## 13. Deploy operators (Phase 1)

```bash
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo add clickhouse-operator https://docs.altinity.com/clickhouse-operator/
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

for r in opentelemetry-operator altinity-clickhouse-operator prometheus-operator; do
  ARGUS_NAMESPACE="$NAMESPACE" ARGUS_IMAGE_REGISTRY="$ACR_LOGIN_SERVER" \
    helmfile apply --selector name="$r"
done

kubectl get pods -n "$NAMESPACE" | grep -E "opentelemetry|clickhouse-operator|prometheus"
```

All three must be `Running` before Phase 2.

---

## 14. Deploy Argus workloads (Phase 2)

Pre-create secrets from Key Vault values:

```bash
kubectl -n "$NAMESPACE" create secret generic argus-clickhouse-secret \
  --from-literal=CLICKHOUSE_PASSWORD="$CLICKHOUSE_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n "$NAMESPACE" create secret generic argus-sso-secret \
  --from-literal=jwt-secret="$JWT_SECRET" \
  --dry-run=client -o yaml | kubectl apply -f -
```

> The chart also templates secrets from `charts/argus/values.yaml` (`secrets.*`,
> `clickhouse.password`). Override them in `values-azure.yaml` or via
> `--set` so the Key Vault values are used, not the repo defaults.

Deploy:

```bash
ARGUS_NAMESPACE="$NAMESPACE" ARGUS_IMAGE_REGISTRY="$ACR_LOGIN_SERVER" \
  helmfile apply --selector name=argus

kubectl get pods -n "$NAMESPACE" -w
```

Check storage came up correctly:

```bash
kubectl get pvc -n "$NAMESPACE"                        # data-storage ... argus-premium, Bound
kubectl get pv -o custom-columns=NAME:.metadata.name,SC:.spec.storageClassName,SIZE:.spec.capacity.storage
```

Expected workloads:

| Pod prefix | Component |
|---|---|
| `chi-argus-clickhouse-*` | ClickHouse (hot PVC + Blob cold) |
| `chk-argus-keeper-*` | ClickHouse Keeper |
| `signoz-*` | UI / query |
| `signoz-otel-collector-*` | Telemetry ingestion |
| `argus-idp-*`, `argus-sso-gateway-*` | SSO / RBAC |
| `argus-rum-collector-*` | RUM / session replay |
| `argus-synthetic-prober-*` | Synthetics |
| `argus-paging-gateway-*` | Paging |
| `argus-correlation-engine-*` | Alert correlation |
| `argus-anomaly-detector-*` | Anomaly detection |
| `argus-llm-service-*` | NL query |
| `argus-s3-*` | SeaweedFS — **absent on Azure** (Blob replaces it) |

---

## 15. Apply retention, tenancy & SSO

### 15.1 Retention / tiering TTLs

Edit TTL days in `deploy/clickhouse/retention-policies.sql` to match your
section 1 table (pattern):

```sql
ALTER TABLE default.otel_logs
  MODIFY TTL toDateTime(Timestamp) + INTERVAL 7  DAY TO VOLUME 'cold',
             toDateTime(Timestamp) + INTERVAL 30 DAY DELETE;
-- repeat for otel_traces and the otel_metrics_* tables
```

Apply:

```bash
POD=$(kubectl -n "$NAMESPACE" get pod -l clickhouse.altinity.com/chi=argus-clickhouse -o name | head -1)
kubectl -n "$NAMESPACE" exec -i "$POD" -- \
  clickhouse-client --password "$CLICKHOUSE_PASSWORD" --multiquery \
  < deploy/clickhouse/retention-policies.sql
```

Verify the policy and disks:

```bash
kubectl -n "$NAMESPACE" exec "$POD" -- clickhouse-client --password "$CLICKHOUSE_PASSWORD" -q \
  "SELECT name, type, path FROM system.disks"
# expect: default (local) and azure_cold (ObjectStorage)

kubectl -n "$NAMESPACE" exec "$POD" -- clickhouse-client --password "$CLICKHOUSE_PASSWORD" -q \
  "SELECT policy_name, volume_name, disks FROM system.storage_policies"
```

Force a test move to prove Blob works:

```bash
kubectl -n "$NAMESPACE" exec "$POD" -- clickhouse-client --password "$CLICKHOUSE_PASSWORD" -q \
  "ALTER TABLE default.otel_logs MOVE PARTITION tuple() TO VOLUME 'cold'"   # or pick a real partition id
az storage blob list --account-name "$STORAGE_ACCOUNT" -c "$STORAGE_CONTAINER" \
  --auth-mode login --num-results 5 -o table
```

### 15.2 Tenancy & SSO

```bash
ARGUS_NAMESPACE="$NAMESPACE" CLICKHOUSE_PASSWORD="$CLICKHOUSE_PASSWORD" \
  bash deploy/tenancy/apply-tenancy.sh

ARGUS_NAMESPACE="$NAMESPACE" JWT_SECRET="$JWT_SECRET" \
  bash deploy/sso/apply-sso.sh
```

---

## 16. Access the UI

Quick (port-forward):

```bash
kubectl -n "$NAMESPACE" port-forward svc/signoz 8080:8080            # SigNoz
kubectl -n "$NAMESPACE" port-forward svc/argus-sso-gateway 8088:8088 # SSO
```

| URL | What |
|---|---|
| `http://localhost:8080` | SigNoz (admin password: `signoz-admin-password` in Key Vault) |
| `http://localhost:8088/sso/login` | SSO login |

Persistent access — internal LB (recommended) or ingress:

```bash
kubectl -n "$NAMESPACE" patch svc signoz -p '{"spec":{"type":"LoadBalancer"}}'
kubectl -n "$NAMESPACE" annotate svc signoz \
  service.beta.kubernetes.io/azure-load-balancer-internal="true" --overwrite
kubectl -n "$NAMESPACE" get svc signoz -w      # wait for EXTERNAL-IP (private IP)
```

For public HTTPS use an ingress controller (Traefik is in the chart:
`ingress.className: traefik`, set `ingress.host`) plus cert-manager. The old
`http_application_routing` addon is retired — don't use it.

Sending telemetry in: apps push OTLP to the collector gateway
(`argus-otel-gateway.<ns>:4317` gRPC / `:4318` HTTP). See
`docs/runbooks/service-onboarding.md`.

---

## 17. Verify the platform

```bash
# all pods healthy
kubectl get pods -n "$NAMESPACE" | grep -v Running | grep -v Completed

# ClickHouse reachable, tiers present
kubectl -n "$NAMESPACE" exec "$POD" -- clickhouse-client --password "$CLICKHOUSE_PASSWORD" -q "SELECT 1"

# data is landing
kubectl -n "$NAMESPACE" exec "$POD" -- clickhouse-client --password "$CLICKHOUSE_PASSWORD" -q \
  "SELECT 'logs', count() FROM default.otel_logs
   UNION ALL SELECT 'traces', count() FROM default.otel_traces
   UNION ALL SELECT 'metrics', count() FROM default.otel_metrics_gauge"

# where do parts live (hot vs cold)
kubectl -n "$NAMESPACE" exec "$POD" -- clickhouse-client --password "$CLICKHOUSE_PASSWORD" -q \
  "SELECT table, disk_name, formatReadableSize(sum(bytes_on_disk)) FROM system.parts
   WHERE active GROUP BY table, disk_name ORDER BY table"
```

Regression suites (with port-forwards active):

```bash
IDP_URL=http://localhost:8089 GATEWAY_URL=http://localhost:8088 bash scripts/test-sso.sh
IDP_URL=http://localhost:8089 GATEWAY_URL=http://localhost:8088 bash scripts/test-tenancy.sh
```

---

## 18. Backups

Cold-tier Blob objects are **not** a backup (ClickHouse owns them; metadata lives
on the hot disk). Back up separately:

1. **Managed Disk snapshots** (hot data + metadata) — Azure Backup for AKS:
   ```bash
   az dataprotection backup-vault create -g "$RG" -v argus-backup-vault -l "$LOCATION" \
     --storage-setting "[{type:'LocallyRedundant',datastore-type:'VaultStore'}]"
   az aks backup --help     # enable AKS Backup extension, daily policy, 14–30 d retention
   ```
2. **ClickHouse native backup to a second Blob container** (consistent, includes
   cold parts):
   ```sql
   BACKUP DATABASE default, DATABASE signoz_metrics
   TO AzureBlobStorage('<connection-or-url>', 'clickhouse-backup', 'daily/2026-01-01');
   ```
   Schedule with a CronJob; use a *separate* container/storage account.
3. Keep Key Vault soft-delete + purge protection on (default for new vaults).

---

## 19. Multi-environment (DEV / STAGING / PROD)

- One resource group, AKS, ACR (or shared ACR), Key Vault, storage account **per
  env**. Re-run sections 3–18 with `ENV=dev|staging|prod`.
- PROD ClickHouse is isolated from non-prod (retention, blast radius).
- Per-cluster OTel agents tag `deployment.environment` and `k8s.cluster.name`;
  spoke clusters forward to the hub gateway. See
  `docs/multi-cluster-onboarding-plan.md`.
- Keep one `charts/argus/values-azure-<env>.yaml` per env (registry, storage
  account, PVC sizes).

---

## 20. Production hardening checklist

- [ ] All secrets random, in Key Vault (section 8); none from repo defaults
- [ ] Workload Identity for Blob; no storage account keys in the cluster
- [ ] Hot disks on `Premium_ZRS`, `reclaimPolicy: Retain`, usage alert at 70%
- [ ] Blob: public access off, TLS 1.2, soft delete on, **no** lifecycle-delete rule
- [ ] Backups configured and a restore tested (section 18)
- [ ] AKS: Entra ID integration (`--enable-aad`), autoscaler (`--enable-cluster-autoscaler --min-count 3 --max-count 10`)
- [ ] Private cluster / internal LB only; NetworkPolicy restricting `argus-system`
- [ ] Defender for Containers enabled
- [ ] Image tags pinned (no `latest` — `clickhouse-keeper`, `seaweedfs` currently use it)
- [ ] Alerts on: ClickHouse disk %, failed TTL moves (`system.part_log`), Blob 403s
- [ ] `TELEMETRY_ENABLED=false`, `REPORT_USAGE=false` on SigNoz (already in chart)

---

## 21. Troubleshooting

| Symptom | Check / fix |
|---|---|
| ClickHouse pod `Pending` | `kubectl describe pvc` — StorageClass missing, or zone mismatch (use ZRS / zonal pool) |
| `azure_cold` disk errors on start | Federated credential subject must be exactly `system:serviceaccount:<ns>:clickhouse`; pod needs label `azure.workload.identity/use: "true"` |
| `403 AuthorizationPermissionMismatch` | Role `Storage Blob Data Contributor` missing/not yet propagated (wait ~5 min), wrong account scope |
| Data never moves to cold | TTL not applied (`SHOW CREATE TABLE`), `ttl_only_drop_parts` + partition not yet old enough, check `system.part_log` |
| Hot disk filling | Lower hot days, raise `move_factor`, or expand PVC (section 9) |
| `ImagePullBackOff` | Image not imported to ACR (section 7), or `--attach-acr` not done |
| Helm upgrade fails on StatefulSet | `volumeClaimTemplates` immutable — expand PVC directly instead |
| Cluster lost cold data after delete | Expected if Blob container wiped; ClickHouse metadata is on hot disk — restore from section 18 |

---

## 22. Implementation checklist (repo changes, phased)

Repo changes the guide above assumes but that are **not done yet**. Do in order;
each phase is independently mergeable.

### Phase 1 — Azure storage in chart (hot + cold)

- [ ] Add `charts/argus/values-azure.yaml` (registry, `azure.*`, `clickhouse.hotStorage`, `clickhouse.keeperStorage`) (§11.4)
- [ ] Add `deploy/azure/storageclass-premium.yaml` (`argus-premium`, `Premium_ZRS`, `Retain`, expandable) (§9)
- [ ] `charts/argus/templates/clickhouse.yaml`: set `storageClassName` + sizes from values for `data-storage` and `keeper-storage` (§11.3)
- [ ] `charts/argus/templates/clickhouse.yaml`: replace `s3_cold` disk with `azure_cold` (`azure_blob_storage`, workload identity); keep policy name `tiered_hot_cold` (§11.2)
- [ ] Mirror same changes in `deploy/clickhouse/clickhouse-ha.yaml` (non-Helm path)
- [ ] Add `charts/argus/templates/clickhouse-sa.yaml` (SA `clickhouse`, `azure.workload.identity/client-id`) + pod label/`serviceAccountName` in podTemplate (§11.1)
- [ ] Add `storage.s3Enabled` flag; wrap `templates/storage.yaml` (SeaweedFS) in `if` so Azure disables it
- [ ] Add `values-azure.yaml` to `argus` release in `helmfile.yaml`
- [ ] Keep SeaweedFS as default for air-gapped/local (no regression on kind/k3d)
- [ ] `helm template` with both values sets renders clean; `helm lint` passes

### Phase 2 — Retention & secrets

- [ ] Parametrize TTL days in `deploy/clickhouse/retention-policies.sql` / `otel-schema.sql` (hot days, total days per signal)
- [ ] Align TTLs with §1 table (logs/traces/raw metrics 7d hot → 30d drop; 1m 30/90; 1h 90/365)
- [ ] Move chart default secrets out of `values.yaml` (`clickhouse.password`, `secrets.*`) to required/`--set` or external secret
- [ ] Add Key Vault → k8s secret path (CSI Secrets Store driver or documented script)
- [ ] Replace `default/networks/ip: "::/0"` ClickHouse user exposure with in-cluster CIDR only
- [ ] Span coverage: decide 100% retention vs tail sampling (keep errors + slow + 10% baseline) in `deploy/otel/gateway.yaml`; add `spanmetrics` connector before sampling; add exporter `sending_queue`/`retry_on_failure` (see "Span coverage & sampling" in §1)

### Phase 3 — Automation

- [ ] `scripts/azure-bootstrap.sh`: RG, AKS, ACR, KV, storage, UAMI, role assignment, federated credential (§3–§10)
- [ ] `deploy.sh --azure` flag: apply StorageClass, use `values-azure.yaml`, skip SeaweedFS + mirror to localhost
- [ ] `scripts/verify-storage.sh`: checks `system.disks`, `system.storage_policies`, parts per disk, Blob objects after forced move (§15.1, §17)
- [ ] Image build/push (`az acr build`) for in-repo images in `deploy/mirror` flow

### Phase 4 — Backup & ops

- [ ] ClickHouse `BACKUP ... TO AzureBlobStorage` CronJob + separate container/account (§18)
- [ ] AKS Backup (disk snapshots) enabled via script/Terraform
- [ ] Alerts: hot disk > 70%, failed TTL moves, Blob 403s (add to `deploy/alerting/prometheus-rules.yaml`)
- [ ] Restore drill documented in `docs/runbooks/` (new `clickhouse-restore.md`)

### Phase 5 — Multi-env & hardening

- [ ] `values-azure-dev/staging/prod.yaml` split (sizes, accounts, registry) (§19)
- [ ] Internal LB annotation + Traefik/cert-manager ingress values (§16)
- [ ] NetworkPolicy for `argus-system`
- [ ] Pin `latest` tags (`clickhouse-keeper`, `seaweedfs`) in `values.yaml` + `images.txt`
- [ ] IaC (Bicep/Terraform) replacing CLI steps, optional
- [ ] ADR: `docs/decisions/ADR-0017-azure-storage-tiering.md` (hot Managed Disk + cold native Blob, why not S3 API / Files)

### Open questions

- Daily ingest (GB/day) → hot PVC size?
- 100% spans or tail sampling?
- Retention per signal (confirm §1 defaults)?
- Zonal AKS node pools (ZRS vs LRS disks)?
- One central ClickHouse or per-env?
- IaC tool: CLI scripts, Bicep or Terraform?
