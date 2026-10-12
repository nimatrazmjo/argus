# Layer Boundaries

The enforceable rules behind `architecture/ARCHITECTURE.md`. `scripts/SCRIPTS.md` →
check-architecture validates these; a violation fails the build and blocks "done." These are
import-direction rules — dependencies point one way only.

> **Deferred until you have the requirement.** While this file has no real rules,
> check-architecture is a permissive no-op (it exits 0), so the loop runs from feature one with
> no architecture defined. The moment you write real rules below, it becomes an enforcing gate.
> Boundaries differ by project type — a full-stack app, a DevOps/IaC repo, and an Airflow
> pipeline each guard different things; `architecture/ARCHETYPES.md` sketches all three. Fill
> from the closest one.

## Allowed dependency direction

<<FILL: draw your project's allowed import direction. The one rule that generalizes: a pure,
framework-free **domain/core** that everything else depends on and that depends on nothing.
Example shape:

    presentation  ->  <ui/interaction>  ->  <local-state>  ->  <client-model>  ->  <api-client>
    domain  <-  api (server)  <-  (network boundary)
    persistence  <-  domain
>>

## The rules (each must be checkable)

<<FILL: one numbered rule per boundary, each phrased so a grep/import-graph check can decide
it. Start from these that generalize to most stacks and adapt:

1. The domain/core package imports nothing framework-specific (no UI framework, no ORM
   client, no HTTP client). Any such import inside it is a violation.
2. UI/interaction code may not import persistence or the server directly.
3. UI mutates state only through the designated command/mutation layer, not ad-hoc calls.
4. Local UI state holds no server truth (viewport/selection/transient flags only); server
   truth lives in the query cache / server.
5. The server is the only caller of persistence; the frontend never imports ORM types.
6. Domain invariants live in the domain, not in controllers or components.
7. No sideways access into another feature's internal state.
8. Core code handles variants via registries, not `switch` over a built-in enum once a
   registry exists (MODULES.md).
>>

## Rationale
The one boundary that matters most: **the domain is pure and shared.** It is the single
definition the UI, the API, and any tooling agree on. Every leak into it forks the truth.

## How to check
Until the app exists, this file is the spec. Once the code exists, implement
check-architecture (contract in `scripts/SCRIPTS.md`) to inspect the import graph and exit
non-zero on any violation. The check runs in `init` and before any feature is marked passed.
