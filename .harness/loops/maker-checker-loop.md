# Maker-Checker Loop

A self-contained build/verify cycle that needs no human in the round. The Maker implements;
the Checker (a separate invocation, so it cannot see the Maker's rationalizations) verifies
against acceptance + rubric; feedback loops back until N consecutive passes or max rounds.
This is `roles.md` turned into an automated cycle, and it is the loop `graph/workflow-graph.md`
draws.

## Components

### Maker prompt (skeleton)
```
You are the Maker. Implement ONLY the active feature in .harness/ROADMAP.md.
Read: AGENTS.md, the feature's sprint-contract.md, architecture docs, layer-boundaries.md,
scope-guard.md. Build the thinnest step that advances the feature. Produce the evidence
each acceptance item needs. Obey boundaries and scope. Do NOT grade your own work. Do NOT
mark the feature passed. Output: what you changed, the exact commands to reproduce evidence,
any contract deviation.
```

### Checker prompt (skeleton)
```
You are the Checker. You did not write this code. Do not trust the Maker's summary.
Re-run every verification command yourself: the FULL suite (not a subset), check-architecture,
and the e2e test for any user-facing flow. Score against .harness/verification/evaluator-rubric.md.
Check acceptance completeness, correctness (probe the applicable .harness/verification/edge-cases.md
categories the Maker skipped; confirm error paths and no regression in COMPLETE features),
boundary+scope compliance, modularity, evidence quality. Look for the skipped item, the empty
assertion, the boundary leak, the flaky/mocked-away e2e. Output: the scored block + verdict
PASS|REVISE. On REVISE, list specific defects tied to acceptance items / rubric lines with the
failing evidence. Do not fix code.
```

### State file
`loop-state.md` — tracks round number, what the Maker changed, the Checker verdict +
defects, and the consecutive-pass counter.

## Cycle
```
round r:
  Maker implements  ->  writes evidence + change summary  ->  updates loop-state
  Checker re-runs checks  ->  scores  ->  verdict
    PASS   -> consecutivePasses++ ; if >= REQUIRED_PASSES -> mark feature passed, exit
    REVISE -> consecutivePasses=0 ; record defects ; Maker addresses them next round
  if r >= MAX_ROUNDS -> stop, escalate to human with the standing defects
```

## Parameters (defaults; tune per feature in loop-state.md)
- `REQUIRED_PASSES = 2` consecutive Checker PASSes (guards against a fluke green).
- `MAX_ROUNDS = 6`.
- Escalate immediately (do not spend rounds) on: a boundary violation the Maker keeps
  reintroducing, or a request that needs a human decision (a hard-stop in AGENTS.md).

## Why a separate Checker invocation
If the same context grades itself, it inherits the Maker's blind spots and its motivation
to be done. A cold Checker re-running the commands is the whole point. When run inside one
session, switch context hard and re-run — do not "remember" that it worked.
