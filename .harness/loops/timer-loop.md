# Timer Loop (Monitoring Heartbeat)

A scheduled, recurring check that watches for problems and fixes the safe ones autonomously,
escalating the rest. Not for building features — for keeping the project healthy between
build sessions. Run every 10–30 minutes while active work is happening, or daily for slower
checks.

## What it checks
```
EVERY 30 min (during active development):
  - does init still run green from a clean state?
  - do typecheck / lint / the FULL test suite pass on the current branch? (regression gate)
  - does the e2e smoke (critical user path) still pass?
  - does check-architecture pass (no new boundary violations)?
  - is ROADMAP.md still well-formed with exactly one active feature?

DAILY:
  - dependency audit (known vulns) — report only
  - dead-code / cleanup scan (scripts/SCRIPTS.md -> cleanup-scanner) — report only
  - is PROJECT_STATE.md stale (older than last commit)? flag it
```

## Resolution policy
- **Fix autonomously** (low risk): a formatting/lint failure, a stale handoff timestamp, a
  malformed json trailing comma, a flaky test with an obvious deterministic fix.
- **Report only** (never auto-fix): failing tests with unclear cause, boundary violations,
  dependency vulnerabilities, anything touching the data model or a public contract.
- **Escalate to human**: init won't go green, repeated failures, or a security finding.

## Loop shape
```
tick -> run checks -> classify findings
  -> auto-fixable? fix, verify the fix, log it
  -> report-only?  append to a findings note, do not touch code
  -> escalate?     stop, write a clear human-readable alert in PROJECT_STATE.md
continue at next interval unless disabled or an escalation fired
```

## Stop / control
- Runs indefinitely at its interval until disabled.
- Any escalation pauses the loop for human review.
- Every human intervention is recorded, so we can see whether the loop runs unattended.

## Scheduling note
Schedule this with a real recurring task (a scheduled task / cron), not an in-process timer,
so it survives session end. It reads the same `.harness` state; it is just a different
trigger.

## What the heartbeat runs (make it real, not just typecheck)
```
- init green from clean state
- typecheck + lint + unit/integration tests
- check-architecture (no boundary violations)
- FULL suite, not only the last feature's tests (regression gate)
- e2e smoke: the critical user path(s) still pass end-to-end
- exactly one IN PROGRESS feature; PROJECT_STATE not stale vs last commit
```
