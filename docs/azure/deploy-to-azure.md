# Argus — Azure AKS Deployment Guide

Step-by-step instructions for deploying Argus onto Azure Kubernetes Service (AKS)
using Azure Container Registry (ACR), Azure Blob Storage, and Azure Key Vault.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Azure Resource Group & Core Services](#2-azure-resource-group--core-services)
3. [AKS Cluster](#3-aks-cluster)
4. [Azure Container Registry (ACR)](#4-azure-container-registry-acr)
5. [Mirror Images into ACR](#5-mirror-images-into-acr)
6. [Azure Key Vault — Secrets](#6-azure-key-vault--secrets)
7. [Azure Blob Storage — ClickHouse Cold Tier](#7-azure-blob-storage--clickhouse-cold-tier)
8. [Connect kubectl to AKS](#8-connect-kubectl-to-aks)
9. [Deploy Helm Operators (Phase 1)](#9-deploy-helm-operators-phase-1)
10. [Deploy Argus Workloads (Phase 2)](#10-deploy-argus-workloads-phase-2)
11. [Apply Tenancy & SSO Seeds](#11-apply-tenancy--sso-seeds)
12. [Access the UI](#12-access-the-ui)
13. [Verify the Platform](#13-verify-the-platform)
14. [Production Hardening Checklist](#14-production-hardening-checklist)

---

## 1. Prerequisites

Install these tools locally before starting:

```bash
# Azure CLI
brew install azure-cli          # macOS
az version                      # verify ≥ 2.60

# kubectl
brew install kubectl
kubectl version --client

# Helm
brew install helm
helm version                    # verify ≥ 3.14

# helmfile
brew install helmfile

# jq (used by several scripts)
brew install jq
```

Log in to Azure:

```bash
az login
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"
```

---

## 2. Azure Resource Group & Core Services

All Argus resources live in one resource group. Pick a region close to your users.

```bash
export RG="argus-rg"
export LOCATION="eastus"          # change to your preferred region
export CLUSTER_NAME="argus-aks"
export ACR_NAME="argusacr"        # must be globally unique, lowercase, no dashes
export KV_NAME="argus-kv"         # must be globally unique
export STORAGE_ACCOUNT="argusstorage"   # must be globally unique, lowercase
export STORAGE_CONTAINER="clickhouse-cold"

# Create resource group
az group create --name "$RG" --location "$LOCATION"
```

---

## 3. AKS Cluster

```bash
az aks create \
  --resource-group "$RG" \
  --name "$CLUSTER_NAME" \
  --node-count 3 \
  --node-vm-size Standard_D4s_v3 \
  --enable-addons monitoring \
  --generate-ssh-keys \
  --network-plugin azure \
  --enable-workload-identity \
  --enable-oidc-issuer
```

> **Node sizing guidance**
> - Minimum: 3 × `Standard_D4s_v3` (4 vCPU / 16 GB) for dev/staging.
> - Production: 3 × `Standard_D8s_v3` (8 vCPU / 32 GB) — ClickHouse is memory-heavy.

Wait for the cluster to be ready (~5 min):

```bash
az aks show --resource-group "$RG" --name "$CLUSTER_NAME" \
  --query provisioningState -o tsv
# expected: Succeeded
```

---

## 4. Azure Container Registry (ACR)

```bash
az acr create \
  --resource-group "$RG" \
  --name "$ACR_NAME" \
  --sku Standard

# Attach ACR to AKS so nodes can pull images without extra secrets
az aks update \
  --resource-group "$RG" \
  --name "$CLUSTER_NAME" \
  --attach-acr "$ACR_NAME"
```

Log in locally so you can push images:

```bash
az acr login --name "$ACR_NAME"
export ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
echo "ACR: $ACR_LOGIN_SERVER"
# e.g. argusacr.azurecr.io
```

---

## 5. Mirror Images into ACR

Argus uses a fixed image list. Import them all into ACR:

```bash
# From the repo root
while IFS= read -r line; do
  # skip blank lines and comments
  [[ -z "$line" || "$line" == \#* ]] && continue
  # skip localhost refs (built locally)
  [[ "$line" == localhost:* ]] && continue

  dest_tag=$(echo "$line" | sed 's|.*/||')   # strip registry prefix
  echo "Importing $line -> $ACR_LOGIN_SERVER/argus/$dest_tag"
  az acr import \
    --name "$ACR_NAME" \
    --source "$line" \
    --image "argus/$dest_tag" \
    --force
done < deploy/mirror/images.txt
```

> `az acr import` pulls from the public registry on Azure's side — no local Docker daemon needed.

---

## 6. Azure Key Vault — Secrets

Store all Argus secrets in Key Vault instead of hardcoding them.

```bash
az keyvault create \
  --name "$KV_NAME" \
  --resource-group "$RG" \
  --location "$LOCATION"

# Store secrets
az keyvault secret set --vault-name "$KV_NAME" \
  --name "clickhouse-password"   --value "argus123"
az keyvault secret set --vault-name "$KV_NAME" \
  --name "jwt-secret"            --value "argus-agency-piv-cac-shared-secret-key-32b"
az keyvault secret set --vault-name "$KV_NAME" \
  --name "rum-ingest-token"      --value "argus-rum-ingest-token-default-32b"
az keyvault secret set --vault-name "$KV_NAME" \
  --name "paging-webhook-token"  --value "argus-paging-webhook-token-32b"
az keyvault secret set --vault-name "$KV_NAME" \
  --name "synthetic-bearer-token" --value "argus-synthetic-bearer-token-32b"
az keyvault secret set --vault-name "$KV_NAME" \
  --name "signoz-admin-password" --value "ArgusAdminPassword123!"
az keyvault secret set --vault-name "$KV_NAME" \
  --name "idp-center-password"   --value "center_pass"
```

Pull secrets back out into env vars for the deploy steps below:

```bash
export CLICKHOUSE_PASSWORD=$(az keyvault secret show \
  --vault-name "$KV_NAME" --name "clickhouse-password" --query value -o tsv)
export JWT_SECRET=$(az keyvault secret show \
  --vault-name "$KV_NAME" --name "jwt-secret" --query value -o tsv)
```

---

## 7. Azure Blob Storage — ClickHouse Cold Tier

Argus uses S3-compatible storage for ClickHouse tiered cold data. Azure Blob Storage
exposes an S3-compatible endpoint.

```bash
az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2

az storage container create \
  --name "$STORAGE_CONTAINER" \
  --account-name "$STORAGE_ACCOUNT"

# Get the connection key
export STORAGE_KEY=$(az storage account keys list \
  --resource-group "$RG" \
  --account-name "$STORAGE_ACCOUNT" \
  --query "[0].value" -o tsv)

export S3_ENDPOINT="https://${STORAGE_ACCOUNT}.blob.core.windows.net"

echo "S3 endpoint : $S3_ENDPOINT"
echo "Storage key : $STORAGE_KEY"
```

Store the key in Key Vault:

```bash
az keyvault secret set --vault-name "$KV_NAME" \
  --name "storage-key" --value "$STORAGE_KEY"
```

---

## 8. Connect kubectl to AKS

```bash
az aks get-credentials \
  --resource-group "$RG" \
  --name "$CLUSTER_NAME" \
  --overwrite-existing

kubectl get nodes   # should list 3 Ready nodes
```

Create the Argus namespace:

```bash
kubectl create namespace argus-system --dry-run=client -o yaml | kubectl apply -f -
```

---

## 9. Deploy Helm Operators (Phase 1)

Override the image registry to point at your ACR. Create a values override file:

```bash
cat > /tmp/azure-registry-override.yaml <<EOF
imageRegistry: ${ACR_LOGIN_SERVER}
EOF
```

Add Helm repos and deploy operators via helmfile:

```bash
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo add clickhouse-operator https://docs.altinity.com/clickhouse-operator/
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

ARGUS_NAMESPACE=argus-system \
ARGUS_IMAGE_REGISTRY="${ACR_LOGIN_SERVER}" \
  helmfile apply --selector name=opentelemetry-operator
ARGUS_NAMESPACE=argus-system \
ARGUS_IMAGE_REGISTRY="${ACR_LOGIN_SERVER}" \
  helmfile apply --selector name=altinity-clickhouse-operator
ARGUS_NAMESPACE=argus-system \
ARGUS_IMAGE_REGISTRY="${ACR_LOGIN_SERVER}" \
  helmfile apply --selector name=prometheus-operator
```

Verify all three operator pods are Running:

```bash
kubectl get pods -n argus-system | grep -E "opentelemetry|clickhouse-operator|prometheus-operator"
```

---

## 10. Deploy Argus Workloads (Phase 2)

Pre-create the Kubernetes secrets from Key Vault values:

```bash
kubectl create secret generic argus-clickhouse-secret \
  -n argus-system \
  --from-literal=CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD}" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic argus-sso-secret \
  -n argus-system \
  --from-literal=jwt-secret="${JWT_SECRET}" \
  --dry-run=client -o yaml | kubectl apply -f -
```

Deploy the full Argus chart:

```bash
ARGUS_NAMESPACE=argus-system \
ARGUS_IMAGE_REGISTRY="${ACR_LOGIN_SERVER}" \
  helmfile apply --selector name=argus
```

Watch rollout progress:

```bash
kubectl get pods -n argus-system -w
```

All pods should reach `Running` within ~5 minutes. Expected workloads:

| Pod prefix | Component |
|---|---|
| `signoz-*` | APM UI |
| `signoz-otel-collector-*` | Telemetry ingestion |
| `chi-argus-clickhouse-*` | ClickHouse HA (2 pods) |
| `argus-idp-*` | Agency SSO IdP |
| `argus-sso-gateway-*` | RBAC gateway |
| `argus-rum-collector-*` | RUM / session replay |
| `argus-synthetic-prober-*` | Synthetic canary checks |
| `argus-paging-gateway-*` | Incident paging |
| `argus-correlation-engine-*` | Alert correlation |
| `argus-anomaly-detector-*` | AIOps anomaly detection |
| `argus-llm-service-*` | NL query / LLM |
| `argus-s3-*` | SeaweedFS cold storage |

---

## 11. Apply Tenancy & SSO Seeds

```bash
# Apply ClickHouse tenant users, RLS policies, and quotas
# (includes tenant_center added in the latest commit)
ARGUS_NAMESPACE=argus-system \
CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD}" \
  bash deploy/tenancy/apply-tenancy.sh

# Rebuild IdP ConfigMap with center.ops@dhs.gov seed and roll the pod
ARGUS_NAMESPACE=argus-system \
JWT_SECRET="${JWT_SECRET}" \
  bash deploy/sso/apply-sso.sh
```

---

## 12. Access the UI

Port-forward to your local machine:

```bash
# Terminal 1 — SigNoz APM dashboard
kubectl -n argus-system port-forward svc/signoz 8080:8080

# Terminal 2 — SSO login portal
kubectl -n argus-system port-forward svc/argus-sso-gateway 8088:8088
```

| URL | What |
|---|---|
| `http://localhost:8080` | SigNoz APM UI — email `admin@argus.internal` / `ArgusAdminPassword123!` |
| `http://localhost:8088/sso/login` | Agency SSO login form |

**Center user login:**

| Field | Value |
|---|---|
| Username | `center.ops@dhs.gov` |
| Password | `center_pass` |

For public access (optional), create an Azure Load Balancer ingress:

```bash
az aks enable-addons \
  --resource-group "$RG" \
  --name "$CLUSTER_NAME" \
  --addons http_application_routing

kubectl patch svc signoz -n argus-system \
  -p '{"spec":{"type":"LoadBalancer"}}'

kubectl get svc signoz -n argus-system --watch
# EXTERNAL-IP will appear once Azure provisions the LB (~2 min)
```

---

## 13. Verify the Platform

Run the full end-to-end regression suite from inside the cluster:

```bash
kubectl run argus-verify \
  --image="${ACR_LOGIN_SERVER}/argus/python:3.12-alpine" \
  --restart=Never \
  --rm -it \
  --env="ARGUS_NAMESPACE=argus-system" \
  -- sh -c "
    pip install -q requests &&
    python /scripts/run_sso_e2e.py &&
    python /scripts/run_tenancy_e2e.py &&
    python /scripts/run_rum_e2e.py
  "
```

Or use the shell-based verify script from outside the cluster (requires port-forwards active):

```bash
IDP_URL=http://localhost:8089 \
GATEWAY_URL=http://localhost:8088 \
  bash scripts/test-sso.sh

IDP_URL=http://localhost:8089 \
GATEWAY_URL=http://localhost:8088 \
  bash scripts/test-tenancy.sh
```

Quick smoke test for the center user:

```bash
TOKEN=$(curl -s -X POST http://localhost:8088/sso/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"center.ops@dhs.gov","password":"center_pass"}' \
  | jq -r '.access_token')

echo "$TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null | jq '{roles,tenant_id}'
# expected: {"roles":["Operator"],"tenant_id":"tenant_center"}
```

---

## 14. Production Hardening Checklist

- [ ] Rotate all default passwords in Key Vault before going live
- [ ] Enable AKS-managed Azure AD integration (`--enable-aad`) for `kubectl` RBAC
- [ ] Set `JWT_SECRET` to a 32-byte random value: `openssl rand -hex 32`
- [ ] Enable Azure Defender for Containers on the AKS cluster
- [ ] Add a Network Policy to restrict pod-to-pod traffic in `argus-system`
- [ ] Set resource `limits` on all workloads (already set in Helm chart — verify via `kubectl describe`)
- [ ] Enable AKS cluster autoscaler (`--enable-cluster-autoscaler --min-count 3 --max-count 10`)
- [ ] Enable Azure Monitor / Log Analytics for cluster-level logs
- [ ] Set `TELEMETRY_ENABLED=false` and `REPORT_USAGE=false` on SigNoz (already in chart — air-gap safe)
- [ ] Back up the ClickHouse PVCs to Azure Backup or replicate cold tier to a second storage account
- [ ] Pin all image tags — no `latest` tags in production (update `values.yaml` with explicit digests)
