# Sprint Contract — F002: ClickHouse HA + object-storage tier

Feature: F002 — ClickHouse HA + object-storage tier
Phase: Phase 01 — Foundation
Date: 2026-10-12

> Filled before building. Maps every acceptance criterion to concrete, reproducible verification checks.

## 1. Scope & Acceptance Criteria
- [x] ClickHouse runs HA (2 shards/replicas appropriate for 10-50 app workload) deployed via Altinity operator (`ClickHouseInstallation` CR).
  - *Evidence*: `kubectl get chi -n argus-system`, `kubectl get pods -n argus-system -l clickhouse.altinity.com/chi=argus-clickhouse` showing 2 ready replicas/pods, and `system.clusters` query demonstrating HA cluster topology.
- [x] Tiered storage policy configured and verified (hot local disk -> cold S3/MinIO tier).
  - *Evidence*: `system.disks` shows both `default` (local) and `s3_cold` (object storage) disks; creating a tiered table and executing `ALTER TABLE ... MOVE PART ... TO DISK 's3_cold'` verified via `SELECT disk_name FROM system.parts WHERE table = ...`.
- [x] Pod restart resilience with zero data loss.
  - *Evidence*: Automated test inserts unique test rows, kills ClickHouse pod(s), awaits pod recovery, and queries to confirm 100% data integrity.
- [x] Edge cases covered:
  - Object store temporarily unreachable -> writes continue to land on local disk without crashing.
  - Replica down -> surviving replica serves reads and writes without outage.
  - Disk pressure threshold simulation -> tiering policy moves cold data to secondary tier.
  - *Evidence*: `./scripts/test-clickhouse-edge-cases.sh` passes all failure path simulations.
- [x] Air-gap compliance: all ClickHouse and supporting images resolved from internal mirror (`localhost:5001/argus/...`).
  - *Evidence*: Image origin check in `init.sh` confirms all ClickHouse pods run from mirror.
- [x] E2E: `N/A — not user-facing` (infrastructure storage tier proven by automated functional tests).
- [x] No regressions: `./scripts/verify.sh` green.

## 2. Edge cases & failure paths (from `verification/edge-cases.md`)
- **Downstream error / storage unreachable**: S3 object storage down/unreachable -> ClickHouse storage policy maintains local `default` disk as primary volume; inserts succeed into hot volume without dropping client connections.
- **State / replica down**: One pod restarted or unavailable -> queries to distributed table continue functioning via remaining replica/shard.
- **State / lifecycle persistence**: Pod abruptly killed via `kubectl delete pod` -> persistent volumes retain table definitions and committed parts; restarted pod re-attaches cleanly.
- **Concurrency / deduplication**: ReplicatedMergeTree handles replicated inserts idempotently across shards.

## 3. E2E scenario(s)
`N/A — not user-facing` (backend data tier; verified via automated SQL test suite executing inserts, kills, queries, and part movements).

## 4. Plan (thinnest vertical slice)
1. Add ClickHouse server and S3/MinIO images to internal mirror catalog (`deploy/mirror/images.txt`) and push to `localhost:5001/argus/*`.
2. Deploy lightweight S3/MinIO service in `argus-system` backed by persistent volume and initialize bucket `argus-cold-storage`.
3. Create declarative `ClickHouseInstallation` CR manifest [`deploy/clickhouse/clickhouse-ha.yaml`](file:///Users/nimatullahrazmjo/workstation/argus/deploy/clickhouse/clickhouse-ha.yaml):
   - 2-node cluster (shards/replicas) with ClickHouse Keeper coordination.
   - Storage configuration declaring `s3_cold` disk and `tiered_hot_cold` storage policy (local hot -> S3 cold).
   - Image set to `localhost:5001/argus/clickhouse-server:24.8.4.13`.
4. Apply the ClickHouseInstallation CR and await status `Completed` / all pods Ready.
5. Create automated test and verification script [`scripts/test-clickhouse-tiering.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-clickhouse-tiering.sh):
   - Asserts cluster topology (`system.clusters`).
   - Asserts storage policy (`system.storage_policies`, `system.disks`).
   - Inserts rows, triggers part move to `s3_cold`, asserts `system.parts.disk_name == 's3_cold'`.
   - Executes kill-pod resilience test and asserts zero data loss.
6. Create [`scripts/test-clickhouse-edge-cases.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-clickhouse-edge-cases.sh) covering replica failover and object-store isolation.
7. Integrate into `scripts/verify.sh` and update tracking files.

## 5. Out of scope (parked, not built)
- OTel Collector pipeline writing OTLP to ClickHouse (F003).
- SigNoz frontend connecting to ClickHouse (F006).

## 6. New dependencies (with justification)
- `clickhouse/clickhouse-server:24.8.4.13`: Production LTS ClickHouse engine.
- S3-compatible object storage (MinIO): S3 API target for cold tiering.

## 7. Risks
- ClickHouse Keeper initialization in small clusters: Mitigated by configuring internal Keeper in ClickHouse configuration templates supported by Altinity operator.
- S3 credentials in air-gapped clusters: Stored as Kubernetes Secret and referenced securely in ClickHouse config.
