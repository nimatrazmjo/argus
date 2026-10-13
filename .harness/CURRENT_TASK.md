# CURRENT TASK

**Feature**: F008 — eBPF safety net (Beyla or Pixie): network-level service map for un-annotated services
**Phase**: Phase 02 — Coverage
**Status**: IN PROGRESS

## Active Work
1. [x] Complete F007: Zero-code auto-instrumentation via OTel Operator + onboarding runbook (100% green).
2. [x] Pre-flight architectural research for F008 (Beyla vs Pixie ADR, image catalog, DaemonSet specs, eBPF security contexts).
3. [ ] Commit F007 on branch `feat/F007`.
4. [ ] Checkout branch `feat/F008`.
5. [ ] Mirror Beyla image (`grafana/beyla:2.2.4` -> `localhost:5001/argus/beyla:2.2.4`) and update `deploy/mirror/images.txt`.
6. [ ] Record ADR-0005 (`docs/decisions/ADR-0005-ebpf-safety-net-beyla.md`).
7. [ ] Deploy Beyla DaemonSet (`deploy/ebpf/beyla.yaml`).
8. [ ] Implement verification test scripts (`scripts/test-ebpf.sh` and `scripts/test-ebpf-edge-cases.sh`) and add to `scripts/verify.sh`.
9. [ ] Run full 17-step `./scripts/verify.sh` and capture evidence in `.harness/evidence/F008/`.

## Next immediate step
Commit `feat/F007` and branch to `feat/F008`.
