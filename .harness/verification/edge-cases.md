# Edge Cases — the standard battery

Correctness is not the happy path. Before a feature is `passed`, its tests must have
*considered* every category below that applies, and the sprint contract must name the ones
that do with the test that covers each. "N/A" is a valid answer; an unconsidered category is
not. The Evaluator treats a missing-but-applicable category as a correctness defect
(rubric criterion 2) and probes the ones the Maker skipped.

## The battery (by category)

**Input / data**
- Empty: empty string, empty list, empty file, zero rows, no results.
- Null / missing / undefined; optional vs required fields.
- Boundary values: 0, 1, -1, max int, off-by-one at limits, first/last element.
- Large / bulk: pagination limits, very long strings, huge payloads, deep nesting.
- Malformed: bad JSON, wrong type, unexpected enum, invalid id/format.
- Unicode / encoding: emoji, RTL, combining chars, whitespace-only, homoglyphs, long names.
- Duplicates: same id twice, repeated submit, unique-constraint collisions.

**State / lifecycle**
- Not-found: id that doesn't exist; deleted-then-referenced.
- Stale / conflicting writes: two edits to one record (last-write-wins vs conflict).
- Idempotency: retrying the same create/update/delete does not double-apply.
- Ordering: out-of-order events; an operation applied before its prerequisite.
- Partial failure: a multi-step operation fails halfway — no half-written state.

**Concurrency**
- Two actors mutating the same resource at once; a race on create.
- Optimistic-lock / version mismatch handled, not silently overwritten.

**Auth / tenancy / permissions**
- Unauthenticated; expired or invalid token.
- Authenticated but not authorized (wrong role) — denied, not leaked.
- Cross-tenant: actor A cannot read/write tenant B's data (isolation).

**Failure / resilience**
- Downstream error/timeout (DB down, upstream 5xx, network drop) — surfaced, logged, retried
  where safe, not swallowed.
- Error path returns a typed error + correct status, never a 200 with a broken body.
- No unhandled rejection / uncaught exception on any of the above.

**UI (if user-facing)**
- Loading, empty, and error states render (not a blank screen or a spinner forever).
- Rapid interaction: double-click, fast repeats, submit-while-pending.
- Keyboard + focus + basic a11y for the new control.
- Reload persistence: state survives a refresh where the acceptance says it should.

## How to use it
- **Planner**: list the applicable categories in the sprint contract and the concrete test
  for each; mark the rest N/A with a word on why.
- **Maker**: write those tests (asserting real behavior) alongside the happy path.
- **Checker**: re-run them and probe the skipped categories. A plausible failing input in an
  applicable category is an automatic REVISE.

## Minimum by feature type (on top of the applicable battery)
- **Data/model**: null/empty, unique-constraint collision, cross-tenant isolation, idempotent
  upsert, migration up **and** down.
- **API**: unauth, unauthorized, not-found, malformed body (validation 4xx), downstream
  failure (5xx path), one happy path — as integration tests.
- **UI**: loading/empty/error states, reload persistence, and one full user flow as an
  **e2e** test (`acceptance-evidence.md`).
- **Cross-cutting** (undo, palette, config): the inverse/replay path and the "nothing to do"
  path.
