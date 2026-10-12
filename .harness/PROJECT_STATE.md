# PROJECT STATE — MASTER FILE

> Read this first, every session. Rewrite it for a cold reader before you stop.

## Where we are
- **Phase**: Phase 01 — Foundation
- **Active feature**: F001 — Cluster baseline + operators (IN PROGRESS)
- **Overall progress**: 0 / 21 features COMPLETE (0%)

## Last verified
- **Date**: 2026-10-12
- **init**: not yet — `scripts/init.sh` is built as part of F001
- **Full suite + check-architecture**: not yet — check-architecture is a no-op until `rules/layer-boundaries.md` is filled
- **E2E**: not yet
- **Git**: branch `master`, commit `<pending first commit>` — harness just scaffolded

## Next step
Write the sprint contract for F001 (`verification/sprint-contract.md`), then implement
`scripts/init.sh` and `scripts/check-architecture.sh` and the Helm install of the three
operators (OTel, Altinity ClickHouse, Prometheus) from the internal mirror. See CURRENT_TASK.md.

## Open blockers
See `BLOCKERS.md`. None yet. Note the air-gap precondition: an internal image/chart mirror must
be reachable before F001 install can pull anything.

## Notes for the next agent
- Archetype is **DevOps/IaC (archetype B)**: `DATA_MODEL.md` / `API_SURFACE.md` are likely N/A.
- Architecture (`ARCHITECTURE.md`, `MODULES.md`) and `rules/layer-boundaries.md` are intentionally
  still placeholders — fill them from archetype B once the layer shape is locked; until then
  check-architecture is a permissive no-op and the loop still runs.
- `CLAUDE.md` Commands are still placeholders: the real toolchain (helm/kubectl + test/e2e
  runner) is decided and wired in F001 — do not guess a package manager before then.
- Product, personas, roadmap (21 features / 5 phases), the phase files, and scope-guard are filled.
