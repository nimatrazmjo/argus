# AGENTS.md — Operating Contract

You are a coding agent building this project. This file overrides your defaults. Read it
fully. If a request conflicts with this contract, follow the contract and say so.

## What this project is
See `product/PRODUCT.md` for the vision and `architecture/ARCHITECTURE.md` for the shape.
Build the product the requirement describes — never a shortcut that fakes the acceptance.

## Read this order, every session (before touching code)
1. `PROJECT_STATE.md` — MASTER FILE. Where the project is right now.
2. `CURRENT_TASK.md` — the one feature to work on and its exact next step.
3. `ROADMAP.md` — all features across the phases, with status.
4. The active phase file under `phases/` — acceptance criteria for the current feature.
5. `DECISIONS.md` + `BLOCKERS.md` — what's decided, what's stuck.
6. **Then inspect the actual code.** The codebase is the source of truth for what EXISTS;
   the tracking files are the source of truth for intended state + history. If they
   disagree: inspect, correct the tracking files, and note the discrepancy in `CHANGELOG.md`.

## The ten rules
1. **Tracking before memory.** Never rely on conversation history. The `.harness/`
   tracking files are the state of the project. Read them first; update them before you stop.
2. **Parallel Tracks with Wave Synchronization Gates.** In multi-agent execution, tasks within the active wave are dispatched across independent parallel tracks (Tracks A through E, detailed in `PARALLEL_EXECUTION_GRAPH.md`). Within a track, tasks execute sequentially; across tracks, subagents execute in parallel. The orchestrator holds synchronization barriers at Wave Gates before unlocking downstream dependent features.
3. **No victory without evidence.** A feature is `COMPLETE` only when every acceptance
   criterion in its phase file is met AND verification is recorded in `CHANGELOG.md`:
   happy path + the applicable `verification/edge-cases.md` battery + error paths + the FULL
   suite green (no regressions) + an e2e test for any user-facing flow
   (`verification/acceptance-evidence.md`). "It should work" is not evidence.
4. **Respect layer boundaries.** Obey `rules/layer-boundaries.md`. Cross-layer imports are
   a defect. `check-architecture` enforces this and a violation blocks "done".
5. **Stay in scope + phase.** `rules/scope-guard.md` lists what is off-limits for the
   current phase. Phases are gated (ROADMAP order). Don't build a later phase's features now.
6. **Modular and expandable.** New types, importers, exporters, and actions register
   against interfaces (`architecture/MODULES.md`); they do not edit the core. If adding a
   feature forces a core edit that a registry should handle, the abstraction is wrong.
7. **Separate maker from checker.** After implementing (maker), switch to the Evaluator
   role (`verification/roles.md`) and score honestly against `verification/evaluator-rubric.md`.
   You may not approve your own work by assertion.
8. **Persist state every session.** Before stopping, update `PROJECT_STATE.md`,
   `CURRENT_TASK.md`, `ROADMAP.md` (+ the phase file), and `CHANGELOG.md`; open/close
   anything in `BLOCKERS.md`; record decisions in `DECISIONS.md`. See `rules/conventions.md`
   and the Session-completion protocol below.
9. **Small, reversible steps.** Thinnest vertical slice that is demonstrable. Commit per
   feature on `feat/<FID>` (or `docs/<slug>`/`chore/<slug>` for harness-only work,
   `rules/conventions.md`) with the message format in `rules/conventions.md`. No drive-by
   refactors. After a feature passes: push, open/reuse a PR, review it, and fix findings
   until clean before starting the next feature (`loops/pr-review-loop.md`).
10. **Observability is not optional.** Structured logs at startup, boundaries, and errors
    (`scripts/SCRIPTS.md` → logger). If you can't see why it failed, add a log before you
    add a fix.

## Statuses (use ONLY these)
`NOT STARTED` · `IN PROGRESS` · `BLOCKED` · `IN REVIEW` · `COMPLETE` · `DEPRECATED`.
No "almost done", "mostly working", "probably fine".

## The loop you run
```
read PROJECT_STATE + CURRENT_TASK + ROADMAP + phase file  ->  confirm the ONE IN PROGRESS feature
  ->  write/confirm sprint-contract  ->  implement (Maker)
  ->  verify (CLAUDE.md Commands: typecheck, lint, FULL tests, check-architecture, e2e)
  ->  score as Checker (evaluator-rubric; edge-cases battery; no regressions)
  ->  pass? record evidence in CHANGELOG, mark COMPLETE in ROADMAP + phase file
      fail? log defects, revise, repeat (bounded rounds)
  ->  push branch, open/reuse PR, review it (code-review, loops/pr-review-loop.md)
      clean? pick next feature
      issues? fix (Maker), commit, push, review again (bounded rounds)
  ->  update PROJECT_STATE + CURRENT_TASK + BLOCKERS  ->  stop cleanly
```
The explicit version, with routing rules, is `graph/workflow-graph.md`.

## Definition of done (per feature)
- Every acceptance criterion in the phase file met.
- Applicable edge/error cases (`verification/edge-cases.md`) covered by tests.
- FULL suite green — no regression in any previously COMPLETE feature (regression gate).
- E2E test passes for every user-facing flow (or contract says "N/A — not user-facing").
- Verification recorded in `CHANGELOG.md` (reproducible command/output or artifact path).
- No layer-boundary violation (`check-architecture` passes).
- Evaluator score >= threshold (`verification/evaluator-rubric.md`).
- `ROADMAP.md` + phase file marked `COMPLETE`; `PROJECT_STATE.md` + `CURRENT_TASK.md`
  updated; committed on `feat/<FID>` (or `docs/<slug>`/`chore/<slug>` for harness-only work).
- Branch pushed, PR opened/reused, reviewed clean, CI (incl. e2e) green, no unresolved
  findings (`loops/pr-review-loop.md`).

When the state is not nominal (dirty tree, red baseline, regression, flaky test, CI drift,
merge conflict, committed secret, blocked feature), follow `loops/failure-modes.md` — each has
a defined response.

## Session-completion protocol (do all of this before you stop)
1. Determine exactly what was implemented and run the appropriate tests.
2. Update the feature status (phase file) and phase status.
3. Update `ROADMAP.md` (checkbox + counts) and `CURRENT_TASK.md`.
4. Update `PROJECT_STATE.md` (current phase/feature, progress, last verified, git commit).
5. Add a `CHANGELOG.md` entry (feature ID + evidence).
6. If the feature just went `COMPLETE`: push the branch, open (or reuse) its PR, review it,
   and fix findings — repeat until clean before touching the next feature
   (`loops/pr-review-loop.md`).
7. Update `BLOCKERS.md` and `DECISIONS.md` if anything changed.
8. Record git branch/commit (or `Working tree: DIRTY`) in `PROJECT_STATE.md`.
9. Clearly set the next task in `CURRENT_TASK.md`.

## Usage / session limits
When you hit a usage or session limit, do not just stop: run the Session-completion
protocol above (commit + update the tracker), then fail over to the other runtime per
`RUNTIME-CONTINUITY.md`. The next runtime resumes from `PROJECT_STATE.md`.

## Hard stops (ask a human)
- A change would delete user data or break a public API contract.
- Scope/acceptance is ambiguous and the files don't resolve it.
- Maker-checker has failed the same feature for the max rounds (`loops/loop-state.md`).

## Tech stack
Locked. No dependency that isn't justified by the active feature; every image/chart is pulled
from the internal mirror (air-gap rule).

- **Runtime target**: Kubernetes (on-prem, air-gapped). All components run in-cluster.
- **Packaging / deploy**: Helm (declarative values / GitOps). Operators: OpenTelemetry
  Operator, Altinity ClickHouse operator, Prometheus Operator.
- **Ingestion**: OpenTelemetry Collector (node DaemonSet + gateway Deployment), OTLP.
- **Storage**: ClickHouse (unified metrics/logs/traces), cold tier to S3/MinIO.
- **UI / APM**: SigNoz (OTel-native) over ClickHouse.
- **eBPF**: Beyla or Pixie (decided in F008, ADR).
- **Profiling**: Pyroscope. **RUM/replay**: OpenReplay or HyperDX (decided in F017).
- **Paging**: webhook to agency incident tooling (ServiceNow); optional Keep.
- **AIOps LLM** (Phase 05): Bedrock within the approved boundary, or on-prem model.
- **Scripts / test / e2e runner**: decided and wired in F001 (do not guess a package manager
  before then); recorded in `CLAUDE.md` -> Commands when set.
