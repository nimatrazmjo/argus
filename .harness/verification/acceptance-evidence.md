# Acceptance Evidence — What Counts

Evidence is the antidote to hallucinated completion. This defines what the Evaluator accepts.
If it is not reproducible, it is not evidence.

## Accepted forms
- **Command + output**: the exact command and its real output (test run, curl against the
  API, migration apply). Preferred for data/API/build features.
- **Test id**: a named test that asserts the behavior, shown passing. Assertions must be
  meaningful — a test that asserts `true` is not evidence.
- **E2E run**: an end-to-end test that drives the real system through a user flow (UI ->
  API -> datastore -> back, or CLI -> real side effect), shown passing, with the recording /
  trace saved under `.harness/evidence/<feature-id>/`. See "End-to-end" below.
- **Screenshot / recording**: for UI behavior, an image or gif saved under
  `.harness/evidence/<feature-id>/`, named for what it shows. Reference the path in
  `CHANGELOG.md`. A screenshot supplements an e2e test; it does not replace one.
- **Artifact**: a generated file (export, migration SQL) checked in or path-referenced.

## End-to-end (e2e) — required for every user-facing flow
A feature a user can reach is not `passed` on unit tests alone. It needs at least one e2e
test that exercises the **real** stack (no mocked API/DB across the boundary it's proving)
for the primary flow, plus the applicable **error/edge** flows from `edge-cases.md` (e.g. the
unauthorized path, the not-found path, the empty state). A valid e2e test:
- drives the system the way a user/client does (real requests, real navigation), and asserts
  an observable outcome — not an internal call count;
- is deterministic (seeded data, awaited state, no `sleep`-and-hope) — a flaky e2e is a defect
  (`failure-modes.md`), not evidence;
- runs in CI, which is the authoritative gate.
Non-user-facing work (a pure library, an internal script) is exempt; say so in the contract.

## No regressions (full-suite gate)
Evidence for a feature includes the **whole** suite green, not just this feature's new tests —
a green subset that hides a broken COMPLETE feature is not evidence. Record that the full
verify (typecheck + lint + full tests + check-architecture + e2e) passed.

## Edge & error paths are part of "works"
"Happy path passes" is a 3/5 at best. The recorded evidence must show the applicable edge and
error cases from `edge-cases.md` covered, not just the nominal input.

## Not accepted
- "It works" / "looks right" / "should be fine."
- A screenshot that does not actually show the acceptance behavior.
- Test output where the test asserts nothing, is skipped, or was edited to pass.
- Evidence the Evaluator cannot reproduce from the recorded command.
- A green build that does not exercise the feature.

## Where evidence lives
- The reproducible command + result: inline in the `CHANGELOG.md` entry.
- Binary artifacts (screenshots, gifs, exports): `.harness/evidence/<feature-id>/`,
  referenced by path.

## Minimum bar per feature type
- Data/model: migration applies clean (up + down) + a test round-tripping the entity +
  unique-constraint and cross-tenant-isolation tests.
- API: integration tests for happy + unauth + unauthorized + not-found + malformed-body +
  one downstream-failure path.
- UI: unit test on the state/logic layer + loading/empty/error states + **one e2e** test of
  the primary user flow + a screenshot/gif of the behavior.
- Cross-cutting (undo, palette, config): a test of the logic layer + the inverse/replay path +
  a capture where visible.

Every feature also clears the **full-suite (no-regression)** and, if user-facing, the **e2e**
gates above. Evidence is part of "done," not paperwork after it. No evidence, no `passed`.
