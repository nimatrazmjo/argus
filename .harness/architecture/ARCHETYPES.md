# Architecture Archetypes — shapes to fill `architecture/` + `layer-boundaries.md` from

Architecture is defined AFTER the requirement, not at scaffold time. When you know what the
repo is, copy the closest shape below into `ARCHITECTURE.md`, `MODULES.md`, and
`rules/layer-boundaries.md` (and `DATA_MODEL.md` / `API_SURFACE.md` only where they apply),
then adapt. The invariant that holds for every archetype: a **pure core** that everything
depends on and that depends on nothing, plus boundaries phrased so `check-architecture` can
decide each one mechanically. Until you write real rules, check-architecture is a no-op and
the loop still runs.

## A. Full-stack application (web + API + DB)
- Layers: presentation -> ui/interaction -> local-state -> client-model -> api-client;
  server -> domain -> persistence. Domain is pure and shared.
- Boundaries: domain imports no framework/ORM/HTTP; UI never imports persistence; UI mutates
  via a command layer; local state holds no server truth; ORM only in the server.
- Arch files: ARCHITECTURE + DATA_MODEL + API_SURFACE + MODULES all apply.
- Registries (MODULES): object/view kinds, importers, exporters, actions.
- E2E: a user flow driven UI -> API -> DB -> back.

## B. DevOps / IaC / platform tooling (Terraform, K8s, CLIs, pipelines)
- Layers: entrypoint (CLI/pipeline) -> orchestration -> providers/adapters (cloud SDK, kubectl,
  terraform) -> a pure core of plan/policy logic. Side-effecting adapters live at the edge.
- Boundaries: the plan/policy core is pure and unit-testable with no cloud calls; only adapters
  touch real infra/network; secrets never in code; env config injected, not hard-coded; a
  dry-run/plan path exists for every apply.
- Arch files: ARCHITECTURE + MODULES apply; DATA_MODEL / API_SURFACE usually **N/A** (delete or
  mark N/A). Add an ENVIRONMENTS.md if you manage several.
- Registries (MODULES): providers/targets, resource types, policy checks.
- E2E: a real (ephemeral/sandbox) plan -> apply -> verify -> destroy, or a plan asserted against
  a golden output.

## C. Airflow / data pipelines
- Layers: DAGs (wiring + schedule only) -> tasks/operators -> hooks/adapters (sources, sinks) ->
  a pure transform/business-logic core. I/O at the edges.
- Boundaries: transforms are pure and unit-testable off-Airflow (no operator imports in core
  logic); DAG files hold no business logic; connections/credentials via Airflow
  connections/vars, never inline; every task idempotent + safely backfillable.
- Arch files: ARCHITECTURE + DATA_MODEL (schemas/contracts) + MODULES apply; API_SURFACE usually
  **N/A**.
- Registries (MODULES): source/sink connectors, transform steps, data-quality checks.
- E2E: a DAG run against seeded inputs asserting outputs + a data-quality gate. Edge cases
  (`verification/edge-cases.md`) map to late/duplicate/out-of-order data, partial failure,
  backfill.

## Pick and adapt
Match the closest archetype, delete the arch files that don't apply, and phrase each boundary
so `check-architecture` can decide it. When none fit, keep the invariant (pure shared core,
mechanically-checkable boundaries) and write the layers your project actually has.
