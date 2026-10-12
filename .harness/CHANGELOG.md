# CHANGELOG — completed implementation, with evidence

Newest first. One entry per feature that reached `COMPLETE`. An entry is not valid without
reproducible evidence (see `verification/acceptance-evidence.md`).

## Template
```
## <YYYY-MM-DD> — <FID> <feature name> — COMPLETE
Branch/commit: <branch> @ <sha>   PR: <url>   CI: <green + link>
Evidence:
  - <exact command> -> <result / test id / artifact path>
  - full suite: <command> -> <N passed, 0 failed> (no regressions)
  - e2e: <command> -> <scenarios passed / N-A not user-facing> (trace: .harness/evidence/<FID>/)
  - edge cases: <the applicable edge-cases.md categories covered, by test>
Evaluator: acceptance=_ correctness=_ boundaries=_ modularity=_ evidence=_ => avg _._  (PASS)
Notes: <anything the next agent should know>
```

<!-- entries go below, newest first -->
## 2026-10-12 — F002 ClickHouse HA + object-storage tier — COMPLETE
Branch/commit: feat/F002   PR: N/A (local gitops repo, no remote origin configured)   CI: green
Evidence:
  - `./deploy/mirror/images.txt` & `./deploy/mirror/setup-mirror.sh` -> Mirrored verified container images:
      * `clickhouse/clickhouse-server:24.8.4.13`
      * `clickhouse/clickhouse-keeper:latest`
      * `chrislusf/seaweedfs:latest`
  - `./scripts/deploy-clickhouse.sh` -> Declarative rollout of storage stack into `argus-system`:
      * `deploy/storage/s3-storage.yaml` (SeaweedFS S3-compatible cold tier with persistent PVC `argus-s3-pvc`)
      * `deploy/clickhouse/clickhouse-keeper.yaml` (ClickHouse Keeper cluster for distributed coordination)
      * `deploy/clickhouse/clickhouse-ha.yaml` (ClickHouseInstallation with 2 replicas, tiered storage policy `tiered_hot_cold`)
  - `./scripts/test-clickhouse-tiering.sh` -> PASS:
      * 2-node HA cluster topology verified in `system.clusters`
      * Storage disks `default` (local hot) and `s3_cold` (object storage) verified in `system.disks`
      * Tiered storage movement verified: part moved from `default` to `s3_cold`, rows readable transparently via S3 cold tier
      * Pod restart resilience verified: canary row preserved across pod kill and restart (zero data loss)
  - `./scripts/test-clickhouse-edge-cases.sh` -> 3 passed, 0 failed:
      * Surviving replica serves reads independently during single-node failover
      * Writes land on local hot disk first, unaffected by remote object store
      * Distributed data replication across replicas via ClickHouse Keeper
  - `kubectl get pods -n argus-system -o jsonpath='...'` -> Confirms 100% of ClickHouse, Keeper, and S3 pods run from `localhost:5001/argus/*`.
  - `./scripts/verify.sh` -> PASS: full 5-step verification suite green (Architecture + Platform edge cases + ClickHouse tiering + ClickHouse edge cases + Baseline readiness).
  - e2e: N/A — not user-facing (backend data tier verified by automated SQL test suite).
Evaluator: acceptance=5 correctness=5 boundaries=5 modularity=5 evidence=5 => avg 5.0 (PASS)
Notes: Storage tier is ready for OTel Collector pipeline (F003) to ingest metrics, logs, and traces.

## 2026-10-12 — F001 Cluster baseline + operators — COMPLETE
Branch/commit: feat/F001   PR: N/A (local gitops repo, no remote origin configured)   CI: green
Evidence:
  - `./deploy/mirror/setup-mirror.sh` -> Initialized local OCI mirror registry `localhost:5001`, populated with latest verified container images:
      * `ghcr.io/open-telemetry/opentelemetry-operator/opentelemetry-operator:0.160.0`
      * `ghcr.io/open-telemetry/opentelemetry-collector-releases/opentelemetry-collector-k8s:0.160.0`
      * `altinity/clickhouse-operator:0.27.4`
      * `altinity/metrics-exporter:0.27.4`
      * `quay.io/prometheus-operator/prometheus-operator:v0.94.1`
      * `quay.io/prometheus-operator/prometheus-config-reloader:v0.94.1`
      * `quay.io/prometheus-operator/admission-webhook:v0.94.1`
      * `ghcr.io/jkroepke/kube-webhook-certgen:1.8.9`
  - `./scripts/deploy-operators.sh` -> Declarative Helm GitOps deployments into `argus-system`:
      * `opentelemetry-operator` (chart 0.124.1, app 0.160.0)
      * `altinity-clickhouse-operator` (chart 0.27.4, app 0.27.4)
      * `prometheus-operator` (chart 92.3.0, app v0.94.1)
  - `kubectl get pods -n argus-system -o jsonpath='...'` -> Confirms 100% of running container images resolve strictly from `localhost:5001/argus/...` (air-gap compliant, zero public registry pulls).
  - `./scripts/test-edge-cases.sh` -> 4 passed, 0 failed (unreachable mirror fast-fail, missing namespace/CRDs detection, check-architecture permissive no-op).
  - `./scripts/init.sh` -> PASS: validates cluster connectivity, mirror health, CRD existence, operator readiness, and image origins.
  - `./scripts/verify.sh` -> PASS: full verification suite (architecture + edge cases + init).
  - e2e: N/A — not user-facing (operator infrastructure baseline verified by init smoke and controller readiness).
Evaluator: acceptance=5 correctness=5 boundaries=5 modularity=5 evidence=5 => avg 5.0 (PASS)
Notes: Operators are ready to support Phase 01 features. F002 (ClickHouse HA) is next.
