# HARNESS-BOOTSTRAP — portable closed-loop build harness

This one file recreates a complete, project-neutral `.harness/` in any repository:
the **loops** (maker-checker, PR-review, timer, goal) and their **failure modes**, the
**workflow graph**, the **roles + rubric + evidence** discipline with a first-class
**e2e requirement + edge-case battery**, the **rules + scripts contracts**, the
**tracking system** (state/roadmap/task/changelog/decisions/blockers), and
**runtime continuity**. It ships **no requirement** — the product vision, the roadmap
features, the phases and the architecture are left as empty placeholders you fill in
after scaffolding.

## How to use

**Agent path (recommended).** Drop this file at the root of the target repo and tell your
coding agent:

> Read `HARNESS-BOOTSTRAP.md` at the repo root and scaffold the harness: create every file it
> defines verbatim at the path in its `FILE:` header (content between `<<<BEGIN` and `END>>>`),
> making directories as needed. Don't clobber anything that already exists. Leave every
> `<<FILL: …>>` placeholder exactly as written — I'll add the product, roadmap, and
> architecture later. Do NOT fill the architecture files or write `layer-boundaries.md` yet;
> that waits until I give you the requirement (`check-architecture` stays a no-op until then).
> When done, run the Self-check below and report the counts, then delete this bootstrap file.

**Manual path.** Each block below is a complete file. Copy the text between `<<<BEGIN`
and `END>>>` into the file named in the `FILE:` header.

## Preconditions & safety (the bootstrap is idempotent)

Before writing anything, the agent checks these and adapts — a failed precondition degrades
gracefully, it does not abort the scaffold:

- **Existing `.harness/`** — do NOT clobber. If a file already exists, leave it and report
  the skip. Only create what is missing. (Re-running this file must be safe.)
- **Git repo** — if the target isn't a git repo, run `git init` first (the loop needs
  commits). If there's no `origin` remote or no `gh` CLI, still scaffold, but note that the
  **PR-review loop is inert until a remote + `gh` exist**; maker-checker + local verify still
  run fully.
- **Default branch** — detect it (`git symbolic-ref --short HEAD`, or `main`/`master`); use
  that name everywhere the docs say `main`.
- **Toolchain** — leave `CLAUDE.md → Commands` as `<placeholders>` unless the repo's manifest
  makes the real commands obvious; never guess a package manager into the docs.

## Self-check (prove the scaffold end-to-end)

After creating the tree, verify the bootstrap actually landed — don't assume:

1. Every `FILE:` path in this document exists on disk (**38 files**).
2. No file still contains the literal `<<<BEGIN` / `END>>>` delimiters (a transcription leak).
3. `graph/graph.json` parses as JSON.
4. Machinery files contain **no** `<<FILL: …>>` markers; only the 9 requirement files +
   `CLAUDE.md` Commands + `AGENTS.md` Tech-stack + the three first-run tracking files do.

Report the counts. Then delete this bootstrap file.

## What you fill in afterward ("the requirement")

Nothing project-specific is written at scaffold time. When you bring the requirement, fill
these — and only these:

**The product + scope (always):**
- `.harness/product/PRODUCT.md`, `.harness/product/PERSONAS.md`
- `.harness/ROADMAP.md` (+ one `phases/PHASE-01-*.md` per phase)
- `.harness/rules/scope-guard.md` (the in-scope / off-limits lists from the ROADMAP)

**The architecture — deferred, and shaped to the project type:**
- `.harness/architecture/ARCHITECTURE.md` + `MODULES.md`, then encode the real import rules in
  `.harness/rules/layer-boundaries.md`.
- `.harness/architecture/DATA_MODEL.md` + `API_SURFACE.md` **only if the archetype has them**
  (a DevOps/IaC or pure-automation repo often marks them N/A).
- Start from the closest shape in `.harness/architecture/ARCHETYPES.md` (full-stack app /
  DevOps-IaC / Airflow-data-pipeline) — that file ships filled in, as guidance.
- Until you write real boundaries, **`check-architecture` is a no-op**, so the loop runs from
  feature one with no architecture yet. Writing the rules flips it to an enforcing gate.

**The toolchain + first run:** set `.harness/CLAUDE.md` → Commands to your commands,
`.harness/AGENTS.md` → Tech stack, then write the first `.harness/PROJECT_STATE.md` +
`.harness/CURRENT_TASK.md` + `loops/loop-state.md`. Everything else is machinery and stays
as-is.

## Tree this produces

```
.harness/
├── README.md                 # what the harness is + read order
├── AGENTS.md                 # operating contract (the rules)  ── machinery
├── CLAUDE.md                 # session bootstrap checklist      ── machinery (Commands = fill)
├── RUNTIME-CONTINUITY.md     # two-runtime failover on limits   ── machinery
├── RUNTIME-SWITCHES.md       # runtime switch ledger (empty)
├── PROJECT_STATE.md          # MASTER: where we are (skeleton)
├── ROADMAP.md                # features × phases (FILL)
├── CURRENT_TASK.md           # the one active feature (skeleton)
├── CHANGELOG.md              # completed-with-evidence history (skeleton)
├── DECISIONS.md              # decision log (skeleton)
├── BLOCKERS.md               # known blockers (skeleton)
├── loops/
│   ├── goal.md               # single-goal iterate-to-done loop     ── machinery
│   ├── maker-checker-loop.md # build/verify cycle, no human         ── machinery
│   ├── pr-review-loop.md     # gate next feature on a clean PR       ── machinery
│   ├── timer-loop.md         # scheduled health heartbeat            ── machinery
│   ├── failure-modes.md      # how the loop handles abnormal states  ── machinery
│   └── loop-state.md         # live loop state (reset template)
├── graph/
│   ├── workflow-graph.md     # the loop drawn: nodes/edges/routing   ── machinery
│   └── graph.json            # machine-readable twin                 ── machinery
├── verification/
│   ├── roles.md              # planner / maker / checker separation  ── machinery
│   ├── evaluator-rubric.md   # the 5-criterion score gate            ── machinery
│   ├── acceptance-evidence.md# what counts as evidence (incl. e2e)   ── machinery
│   ├── edge-cases.md         # the standard edge-case battery        ── machinery
│   └── sprint-contract.md    # per-feature contract (blank template)
├── rules/
│   ├── conventions.md        # ids/git/evidence/session hygiene      ── machinery
│   ├── scope-guard.md        # phase leash (frame kept, body FILL)
│   └── layer-boundaries.md   # import rules (frame kept, body FILL)
├── scripts/
│   └── SCRIPTS.md            # init/check/logger/… contracts         ── machinery
├── state/
│   └── clean-state-checklist.md                                      ── machinery
├── product/
│   ├── PRODUCT.md            # (FILL)
│   └── PERSONAS.md           # (FILL)
└── architecture/
    ├── ARCHETYPES.md         # 3 project shapes to fill from         ── machinery
    ├── ARCHITECTURE.md       # (FILL — after requirement)
    ├── DATA_MODEL.md         # (FILL — optional by archetype)
    ├── API_SURFACE.md        # (FILL — optional by archetype)
    ├── MODULES.md            # (FILL — after requirement)
    └── decisions/
        └── ADR-template.md   # generic ADR template                 ── machinery
```

Statuses used everywhere: `NOT STARTED` · `IN PROGRESS` · `BLOCKED` · `IN REVIEW` ·
`COMPLETE` · `DEPRECATED`. Feature ids are `F001`, `F002`, … Branches are `feat/<FID>`
(or `docs/<slug>`/`chore/<slug>` for harness-only work).

═══════════════════════════════════════════════════════════════════════════════════════
                                    MACHINERY
═══════════════════════════════════════════════════════════════════════════════════════

FILE: .harness/README.md
<<<BEGIN
# Project Harness

This is the **harness** for building this project. A harness gives the model a closed-loop
working system so it builds the right thing, verifies its own work, and — through the
persistent tracking system below — survives across sessions without relying on
conversation history.

**There is no application code here.** This folder is a persistent tracking system +
rules + specs. A coding agent reads it, then writes the app one verified feature at a time.

## Read order (every session starts here)
1. `PROJECT_STATE.md` — **MASTER FILE.** Where the project is. Read this before anything.
2. `CURRENT_TASK.md` — the one feature to work on next.
3. `ROADMAP.md` — all features across the phases, with status.
4. The active `phases/PHASE-XX-*.md` — acceptance criteria.
5. `DECISIONS.md` + `BLOCKERS.md`, then inspect the real code.

## Layout
```
.harness/
├── PROJECT_STATE.md   # MASTER: where we are (read first)
├── ROADMAP.md         # all phases/features + status (source of truth for scope)
├── CURRENT_TASK.md    # the one feature in progress + next step
├── CHANGELOG.md       # completed-implementation history (evidence)
├── DECISIONS.md       # decision log (indexes the ADRs)
├── BLOCKERS.md        # known blockers
├── AGENTS.md          # operating contract (the rules)
├── CLAUDE.md          # session bootstrap checklist
├── RUNTIME-CONTINUITY.md # runtime failover on session limits
├── RUNTIME-SWITCHES.md   # runtime switch ledger
├── phases/            # PHASE-01..N — feature defs + acceptance criteria
├── product/           # PRODUCT.md, PERSONAS.md (the vision)
├── architecture/      # ARCHITECTURE, DATA_MODEL, API_SURFACE, MODULES + decisions/ (ADRs)
├── rules/             # layer-boundaries, scope-guard, conventions
├── verification/      # roles, evaluator-rubric, sprint-contract, acceptance-evidence
├── loops/             # goal, timer, maker-checker, pr-review + loop-state
├── graph/             # workflow-graph (+ json) — the loop, drawn
└── scripts/           # SCRIPTS.md — automation contracts (specs, not code)
```

## The tracking system (why it exists)
The project must not depend on chat history to know what's done. `PROJECT_STATE.md`
answers "where am I?", `ROADMAP.md` answers "where am I going?", `CURRENT_TASK.md`
answers "what do I do now?". After implementing and verifying, the agent updates the
tracking files and picks the next task. A brand-new session can enter the repo and
continue with no prior context.

## The idea in one line
Rules-first entry points (`AGENTS.md`/`CLAUDE.md`/`rules/`), an agent-readable workspace
(this tree), multi-session continuity (the tracking files), runtime feedback + scope
control (`rules/` + `scripts/`), self-verification + role separation (`verification/`),
automated loops (`loops/`), and the workflow drawn as a graph (`graph/`).
END>>>

FILE: .harness/AGENTS.md
<<<BEGIN
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
2. **One feature at a time.** Work only the single feature that is `IN PROGRESS` (named in
   `PROJECT_STATE.md`, detailed in `CURRENT_TASK.md`). Do not start the next until the
   current one is verified.
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
<<FILL: the locked stack for this project — languages, frameworks, datastore, package
manager. Keep it here so every session honors the same choices. No dependency that isn't
justified by the active feature.>>
END>>>

FILE: .harness/CLAUDE.md
<<<BEGIN
# CLAUDE.md — Session Bootstrap

Quick reference. `AGENTS.md` is the full contract; this is the checklist you run every session.

## On session start (in order)
1. Read `PROJECT_STATE.md` — the master file. Where we are.
2. Read `CURRENT_TASK.md` — the one feature + its exact next step.
3. Read `ROADMAP.md` — the feature list + statuses.
4. Read the active phase file under `phases/` — acceptance criteria.
5. Read `DECISIONS.md` + `BLOCKERS.md`.
6. Run `init` (see `scripts/SCRIPTS.md`) to confirm a clean baseline.
7. **Inspect the actual code.** Never trust the tracking files blindly — the codebase is
   the truth for what exists. If they disagree, correct the tracking files and note it in
   `CHANGELOG.md`.

## The one rule you break most often
Work the ONE feature that is `IN PROGRESS`. Evidence before you move on. Don't "quickly
also add" the next thing.

## Where things live
| I need to know... | Read |
|---|---|
| Where the project is right now | `PROJECT_STATE.md` (master) |
| What to do next | `CURRENT_TASK.md` |
| The whole feature list + status | `ROADMAP.md` |
| Acceptance for the current feature | the active `phases/PHASE-XX-*.md` |
| What's been shipped | `CHANGELOG.md` |
| What's decided (don't relitigate) | `DECISIONS.md` (+ `architecture/decisions/` ADRs) |
| What's stuck | `BLOCKERS.md` |
| Why / for whom | `product/PRODUCT.md`, `product/PERSONAS.md` |
| How it's structured / the data shape | `architecture/ARCHITECTURE.md`, `DATA_MODEL.md` |
| What I may import | `rules/layer-boundaries.md` |
| What's off-limits now | `rules/scope-guard.md` |
| How I prove it works | `verification/evaluator-rubric.md`, `acceptance-evidence.md` |
| The edge cases I must cover | `verification/edge-cases.md` |
| What to do when state is abnormal | `loops/failure-modes.md` |

## Commands
<<FILL: replace with your toolchain. These are the exact commands `init`, the loops, and
the Checker run. Keep this table current — it's the first thing the next agent needs.>>

| Action | Command |
|---|---|
| Install | `<install>` |
| Dev server | `<dev>` |
| Typecheck | `<typecheck>` |
| Lint | `<lint>` |
| Test (full suite) | `<test>` |
| E2E | `<e2e>` (real-stack end-to-end; runs in CI) |
| Build | `<build>` |
| Verify baseline | `./scripts/init.sh` (install + build + typecheck + lint + full test + check-architecture + e2e smoke) |
| Check boundaries | `<check-architecture>` (`scripts/check-architecture.sh`) |
| Progress % | see `scripts/SCRIPTS.md` → progress-counter |

## Current target
<<FILL: the active phase + feature, e.g. "Phase 01 — Foundation. Feature F001." Details
live in `CURRENT_TASK.md`.>>

## Before you stop
Run the Session-completion protocol in `AGENTS.md`: update PROJECT_STATE, CURRENT_TASK,
ROADMAP (+ phase file), CHANGELOG, BLOCKERS/DECISIONS as needed; leave the tree clean
(`state/clean-state-checklist.md`); commit on `feat/<FID>` (or `docs/<slug>`/`chore/<slug>`
for harness-only work). If the feature just went COMPLETE: push, open/reuse the PR, review
it, fix findings, and repeat until clean before starting the next feature
(`loops/pr-review-loop.md`).
END>>>

FILE: .harness/loops/goal.md
<<<BEGIN
# Goal Loop

The first step from manual driving to automation: hand the agent a goal with a hard finish
line and let it iterate until done or a stop condition trips. Use this to complete a single
feature (or slice) without babysitting.

## Contract
```
GOAL:        <one feature or slice, e.g. "F001 passes">
DONE WHEN:   every acceptance item in the phase file for this feature is met
             AND evidence recorded AND Evaluator PASS (>=4.0, no 1s)
VERIFY WITH: the FULL verify (CLAUDE.md → Commands: typecheck + lint + full test +
             check-architecture + e2e) + the feature's edge/error tests + its sprint-contract checks
STOP AFTER:  15 turns  OR  90 minutes  OR  3 consecutive Evaluator REVISEs on the same defect
CONSTRAINTS: obey scope-guard.md; one feature only; no new deps without contract justification;
             never mark passed without evidence; never edit .harness rules to make a check pass;
             on any abnormal state (dirty tree, red init, regression, flaky test) follow failure-modes.md
ON STOP:     update ROADMAP.md + CHANGELOG.md + PROJECT_STATE.md, commit, report why it stopped
```

## How it runs each turn
1. Read state (PROJECT_STATE, CURRENT_TASK, sprint contract).
2. Advance the feature by the smallest demonstrable step.
3. Run VERIFY. Capture output as evidence.
4. Switch to Evaluator, score against the rubric.
5. PASS -> record evidence, mark passed, exit loop. REVISE -> log defect, continue.
6. Check stop conditions. If tripped, do ON STOP and halt for human review.

## Notes
- The goal must be *verifiable*, not aspirational. "Make it nice" is not a goal;
  "F009 acceptance met" is.
- The loop does not get to redefine DONE. That is fixed by the feature's acceptance +
  sprint contract.
- If it stops on turns/time rather than success, that is useful data, not failure — it
  means the feature was mis-sized or blocked. Note which in PROJECT_STATE.md.
END>>>

FILE: .harness/loops/maker-checker-loop.md
<<<BEGIN
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
END>>>

FILE: .harness/loops/pr-review-loop.md
<<<BEGIN
# PR Review Loop

Runs after maker-checker passes and `record` writes evidence. Local checks + a self-scored
rubric are not the same as a diff a reviewer actually looked at. This loop closes that gap:
it gates moving to the next feature on a clean PR, not just a clean local run.

## Cycle
```
after record (feature passed maker-checker):
  push branch to origin
  open a PR if none exists for this branch (reuse if one does — never open a second)
  review the PR (code-review; a Checker-style pass over the diff, not self-grading)
    CLEAN  -> exit loop, proceed to next feature / handoff
    ISSUES -> fix (Maker) -> commit -> push (same branch/PR) -> review again
  if issues persist for MAX_PR_ROUNDS -> escalate to human with standing findings
```

## Components

`<branch>` is `feat/<FID>` for a ROADMAP feature, or `docs/<slug>`/`chore/<slug>` for
harness-only tooling work (`rules/conventions.md`'s branch-naming exception). `<name>` is
the FID, or the branch's slug for harness-only work.

### Push
`git push -u origin <branch>` (plain `git push` once upstream is set). Never force-push a
shared branch.

### Open / reuse PR
`gh pr create --base main --head <branch> --title "<type>(<scope>): <desc>"` — title
follows the commit convention (`rules/conventions.md`). Body is the write-up at
`.harness/reviews/<name>-PR.md` — write that file first, pass it as `--body-file`. Check
`gh pr list --head <branch>` before creating; if one is open, push updates to it instead.

### Review
Run a Checker-style `code-review` pass against the branch/PR diff. Same principle as the
Checker in `maker-checker-loop.md`: it must not just trust the Maker's summary of its own
diff. Record findings in `.harness/reviews/<name>-review.md`.

### Fix
Findings get addressed as the Maker, committed, and pushed to the same branch — never a new
PR, never a force-push. Then review again.

## Parameters
- `MAX_PR_ROUNDS = 4` (a round here is push+review+fix, not a full maker-checker cycle —
  keep it separate from `MAX_ROUNDS` in `maker-checker-loop.md`).

## Gate
The next feature does not start (`plan` for the next FID) until the current feature's PR is
clean **and CI is green** (the full suite + e2e in CI, which is authoritative — see
`loops/failure-modes.md` "local green, CI red"). This is `AGENTS.md` rule 2 ("one feature at a
time") extended past the local check to the PR — a feature that passed maker-checker but has an
open PR with unresolved findings or red CI is not done.

## Conflicts with the default branch
If the branch falls behind and conflicts, rebase (or merge) the default branch in, re-run the
full suite + e2e locally, then push — never force-push a shared branch (`failure-modes.md`).

## Why after record, not before
Maker-checker already proves correctness + evidence locally. Doing the PR after `record`
means every PR opened describes a feature already proven, not a WIP diff — the PR review is
one more independent pass (real CI checks, a fresh look at the diff), not a substitute for
the local one.
END>>>

FILE: .harness/loops/timer-loop.md
<<<BEGIN
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
END>>>

FILE: .harness/loops/failure-modes.md
<<<BEGIN
# Failure Modes — how the loop handles abnormal states

The happy loop lives in `maker-checker-loop.md` and `graph/workflow-graph.md`. This file is
what to do when the state is *not* nominal. Each entry is a defined response, not a judgment
call, so the loop behaves the same every run. When one of these fires, note it (CHANGELOG or
BLOCKERS) so a cold agent sees it happened.

## At session start (read-state)
- **Dirty working tree** (uncommitted changes from a prior/other runtime): do NOT build on it
  blind. `git status` + read the diff; reconcile against `PROJECT_STATE.md`. If it's a
  coherent in-progress step for the active feature, continue it; if it's unknown, stash it to
  a `wip/<date>` branch and note it in `BLOCKERS.md`. Never discard without recording.
- **`init` is red**: fixing it IS the first task — before any feature work. A red baseline
  invalidates every downstream check.
- **More than one `IN PROGRESS` feature** (invariant violation): stop. Keep the one that
  matches `PROJECT_STATE.md`; set the others to their true status; note the fix in
  `CHANGELOG.md`. The single-active-feature invariant is load-bearing.
- **Tracking vs code disagree**: the codebase is truth for what EXISTS; correct the tracking
  files and note the discrepancy (`AGENTS.md`).
- **Phase / dependency gate not met**: the active feature depends on an incomplete earlier
  one, or its phase isn't unlocked. Don't build ahead — mark it BLOCKED with the dependency,
  or correct the active feature to the real next one (`scope-guard.md`).

## During build (implement / verify)
- **Regression in a previously COMPLETE feature**: the FULL suite (not just this feature's
  tests) must stay green. A regression is a hard defect — fix it as part of this feature or
  revert the change; never mark passed with a red full suite. This is the **regression gate**.
- **Boundary violation**: `rollback` to the last clean commit, then re-implement within
  bounds (graph rollback edge). If the Maker reintroduces the same violation, escalate — do
  not spend rounds.
- **No clean commit to roll back to** (first feature, nothing green yet): reset the offending
  change by hand to the last compiling state; if none exists, the feature was started wrong —
  re-plan the thinnest slice.
- **Flaky test**: a re-run that goes green is not a pass. Confirm the non-determinism, find
  the root cause (timing, ordering, shared state, real clock/network/random), fix it
  deterministically, and record the fix. Quarantining without a fix is a REVISE.
- **Secret / `.env` / generated artifact staged**: stop, unstage, add to `.gitignore`; if it
  was ever committed, rotate the secret and scrub history. A committed secret is a
  clean-state red flag and a hard stop.

## At the gate (evaluate / record / PR)
- **Checker PASS you don't trust**: re-run cold in a clean checkout. Trust the reproduced
  command, not the memory that it worked.
- **Local green, CI red**: environment drift (native deps, DB, env vars, runtime version). CI
  is authoritative for full verification — reconcile to CI, don't override it. Reinstall /
  rebuild native deps for the platform (`RUNTIME-CONTINUITY.md`).
- **Branch conflicts with the default branch**: rebase (or merge) it into the feature branch,
  re-run the full suite + e2e, then push. Never force-push a shared branch.
- **PR findings persist past `MAX_PR_ROUNDS`**: escalate with the standing findings; do not
  keep looping or silently merge.

## Anytime
- **BLOCKED**: record it in `BLOCKERS.md` (what would unblock it), set the feature status
  BLOCKED, then either pick up an unblocked feature in the same phase or stop cleanly — never
  fake progress around a blocker.
- **Usage / session limit**: run the Session-completion protocol and fail over
  (`RUNTIME-CONTINUITY.md`). Never stop mid-edit with a dirty tree.
- **Scope temptation**: park it in `BLOCKERS.md` / `ROADMAP.md`; stay on the active feature.
END>>>

FILE: .harness/loops/loop-state.md
<<<BEGIN
# Loop State

Live state for the maker-checker loop. Overwrite the "Current" block each round; append
finished features to History. A cold agent reads this to know which round it is on. The
active feature also lives in `../CURRENT_TASK.md`; keep them consistent.

## Parameters (current feature)
- Feature: <<FILL: first feature id, e.g. F001 — <name>>>
- REQUIRED_PASSES: 2
- MAX_ROUNDS: 6

## Current
- Round: 0
- consecutivePasses: 0
- Last Maker change: none (harness scaffolded)
- Last Checker verdict: none
- Standing defects: none
- Next action: write the sprint contract for the first feature

## History
```
(feature id | rounds used | final verdict | date)
--- none yet ---
```

## Escalations
```
(date | feature | reason | resolution)
--- none yet ---
```
END>>>

FILE: .harness/graph/workflow-graph.md
<<<BEGIN
# Workflow Graph

The maker-checker loop, drawn. A graph is not a new invention here; it is what the loop
becomes once it has branches, rollbacks, and a human escape hatch. This is the authoritative
execution model: nodes are steps, edges are transitions, and routing rules decide the next
node from shared state. `graph.json` is the machine-readable twin.

## Diagram

```mermaid
flowchart TD
    START([session start]) --> READ[read-state]
    READ -->|nominal| PLAN[plan / sprint-contract]
    READ -->|dirty tree / red init / >1 active| REPAIR[reconcile: failure-modes]
    REPAIR --> PLAN
    PLAN --> IMPL[implement - Maker]
    IMPL --> VERIFY[verify: typecheck, lint, FULL test, check-architecture, e2e]
    VERIFY --> EVAL{evaluate - Checker}
    VERIFY -->|regression / e2e fail| IMPL
    EVAL -->|REVISE| IMPL
    EVAL -->|PASS, passes < required| IMPL
    EVAL -->|PASS, passes >= required| RECORD[record evidence + mark passed]
    RECORD --> PUSH[push branch]
    PUSH --> OPENPR[open / reuse PR]
    OPENPR --> PRREVIEW{review PR}
    PRREVIEW -->|issues| PRFIX[fix - Maker]
    PRFIX --> PUSH
    PRREVIEW -->|clean| NEXT{more features in slice?}
    NEXT -->|yes| PLAN
    NEXT -->|no| HANDOFF[update handoff + clean state]
    HANDOFF --> STOP([stop])

    VERIFY -->|boundary violation| ROLLBACK[revert to last clean commit]
    ROLLBACK --> IMPL
    EVAL -->|max rounds hit / hard-stop| HUMAN[[escalate to human]]
    PLAN -->|scope ambiguous| HUMAN
    PRREVIEW -->|issues, max PR rounds hit| HUMAN
    HUMAN --> STOP
```

## Nodes
| Node | Responsibility | Input | Output | Type |
|---|---|---|---|---|
| read-state | Load PROJECT_STATE, CURRENT_TASK, sprint contract; check start invariants | `.harness/*` | active feature + context | code (deterministic) |
| repair | Reconcile an abnormal start state (`loops/failure-modes.md`) | dirty tree / red init / >1 active | clean, single-active baseline | agent |
| plan | Fix "done": write/confirm sprint contract | active feature, docs | signed sprint-contract | agent (Planner) |
| implement | Build the thinnest step, produce evidence | sprint contract | code + evidence | agent (Maker) |
| verify | Run typecheck, lint, FULL suite (regression gate), check-architecture, e2e; capture output | code | check results | code (deterministic) |
| evaluate | Score against rubric, re-run checks | code + evidence + results | score + verdict | agent (Checker) |
| record | Write evidence, set status passed | verdict PASS | updated ROADMAP + progress | code + agent |
| push | Push branch to origin | committed evidence | branch on remote | code (deterministic) |
| open-pr | Open PR if none exists, else reuse | branch on remote | PR number/url | code (deterministic) |
| pr-review | Review the PR diff (code-review) | PR | findings or clean | agent (Checker) |
| pr-fix | Address PR findings | findings | code + evidence | agent (Maker) |
| rollback | Revert to last clean commit on hard violation | dirty tree | clean tree | code (deterministic) |
| handoff | Rewrite PROJECT_STATE, run clean-state checklist | slice complete | clean, documented repo | agent |
| escalate | Stop and write a human-readable alert | blocker | alert in PROJECT_STATE | agent |

## Edges
| From | To | Type | Condition |
|---|---|---|---|
| read-state | plan | standard | start state nominal |
| read-state | repair | conditional | dirty tree, red init, or >1 IN PROGRESS |
| repair | plan | standard | baseline clean + single active feature |
| plan | implement | standard | contract signed |
| plan | escalate | conditional | scope/acceptance ambiguous |
| implement | verify | standard | step complete |
| verify | evaluate | standard | checks ran |
| verify | implement | rollback | regression in a COMPLETE feature, or e2e/edge test fails |
| verify | rollback | rollback | boundary violation detected |
| rollback | implement | standard | tree clean again |
| evaluate | implement | rollback | verdict REVISE, or PASS but consecutivePasses < required |
| evaluate | record | conditional | verdict PASS and consecutivePasses >= required |
| evaluate | escalate | conditional | max rounds hit or hard-stop |
| record | push | standard | always |
| push | open-pr | standard | always |
| open-pr | pr-review | standard | always |
| pr-review | pr-fix | conditional | findings present, prRound < MAX_PR_ROUNDS |
| pr-fix | push | standard | fixes committed (loop) |
| pr-review | plan | conditional | clean and more features remain in slice |
| pr-review | handoff | conditional | clean and slice complete |
| pr-review | escalate | conditional | findings present and prRound >= MAX_PR_ROUNDS (checked before pr-fix; a clean review never escalates) |
| handoff | stop | standard | always |
| escalate | stop | standard | always |

## Shared state (every node reads/writes this)
```
activeFeatureId        # from ROADMAP.md
startState             # nominal | dirty-tree | red-init | multi-active (routes to repair)
sprintContract         # the signed contract for the active feature
codeChanges            # what the Maker produced this round
verifyResults          # typecheck/lint/FULL-test/check-architecture/e2e output
regressionDetected     # a COMPLETE feature's test went red this round
e2eVerdict             # PASS | FAIL | N/A (not user-facing)
evaluatorVerdict       # PASS | REVISE
evaluatorScore         # avg + per-criterion
consecutivePasses      # counter toward REQUIRED_PASSES
round                  # current round; guarded by MAX_ROUNDS
standingDefects        # open defects from the Checker
prRound                # current PR review round; guarded by MAX_PR_ROUNDS
prFindings             # open findings from the last PR review
prVerdict              # CLEAN | ISSUES
```
Concrete values live across `ROADMAP.md`, `verification/sprint-contract.md`, and
`loops/loop-state.md` (round, consecutivePasses, standingDefects). The graph does not add a
new store. `prRound`/`prFindings`/`prVerdict` live as prose in each round's
`## PR Review — round N` section of `.harness/reviews/<FID>-review.md`; move them into
`loop-state.md` if a cold agent ever needs to resume mid-PR-round.

## Routing rules (plain if-then, the execution logic)
```
if read-state finds dirty tree/red init/>1 active -> repair (failure-modes) -> plan
if verify detects boundary violation      -> rollback
if verify finds a regression or e2e/edge failure -> implement (fix, round++)
if verify passed                          -> evaluate
if evaluate == REVISE                     -> implement (round++)
if evaluate == PASS and passes <  required -> implement (round++)
if evaluate == PASS and passes >= required -> record
if record                                 -> push -> open-pr -> pr-review
if pr-review has findings and prRound >= MAX_PR_ROUNDS -> escalate (checked first)
if pr-review finds findings               -> pr-fix -> push (prRound++)
if pr-review clean and more features left -> plan (next feature)
if pr-review clean and slice complete     -> handoff
if round >= MAX_ROUNDS or hard-stop       -> escalate
if plan finds scope ambiguous             -> escalate
```

## Why draw it
Two payoffs. First, the branches (rollback on violation, escalate on max-rounds, the
consecutive-pass gate) are explicit instead of buried in an agent's judgment, so the loop
behaves the same every run. Second, it is the seed of real graph-runner orchestration later
(LangGraph-style) if you automate beyond a single agent: these nodes and edges map straight
onto it.
END>>>

FILE: .harness/graph/graph.json
<<<BEGIN
{
  "name": "build-loop",
  "description": "Maker-checker build loop. Machine-readable twin of workflow-graph.md.",
  "version": "1.0.0",
  "entry": "read-state",
  "state": [
    "activeFeatureId", "startState", "sprintContract", "codeChanges", "verifyResults",
    "regressionDetected", "e2eVerdict",
    "evaluatorVerdict", "evaluatorScore", "consecutivePasses", "round", "standingDefects",
    "prRound", "prFindings", "prVerdict"
  ],
  "params": { "REQUIRED_PASSES": 2, "MAX_ROUNDS": 6, "MAX_PR_ROUNDS": 4 },
  "nodes": [
    { "id": "read-state", "type": "code",  "does": "load PROJECT_STATE, CURRENT_TASK, sprint contract; check start invariants" },
    { "id": "repair",     "type": "agent", "does": "reconcile abnormal start state (failure-modes.md)" },
    { "id": "plan",       "type": "agent", "role": "Planner",   "does": "write/confirm sprint contract" },
    { "id": "implement",  "type": "agent", "role": "Maker",     "does": "build thinnest step + evidence" },
    { "id": "verify",     "type": "code",  "does": "typecheck, lint, FULL test (regression gate), check-architecture, e2e" },
    { "id": "evaluate",   "type": "agent", "role": "Checker",   "does": "re-run checks, score against rubric" },
    { "id": "record",     "type": "code",  "does": "write evidence, mark feature passed" },
    { "id": "push",       "type": "code",  "does": "push branch to origin" },
    { "id": "open-pr",    "type": "code",  "does": "open PR if none exists, else reuse" },
    { "id": "pr-review",  "type": "agent", "role": "Checker",   "does": "review PR diff (code-review)" },
    { "id": "pr-fix",     "type": "agent", "role": "Maker",     "does": "address PR findings, commit" },
    { "id": "rollback",   "type": "code",  "does": "revert to last clean commit" },
    { "id": "handoff",    "type": "agent", "does": "rewrite handoff, run clean-state checklist" },
    { "id": "escalate",   "type": "human", "does": "stop and alert a human" },
    { "id": "stop",       "type": "terminal" }
  ],
  "edges": [
    { "from": "read-state", "to": "plan",      "when": "start_state_nominal" },
    { "from": "read-state", "to": "repair",    "when": "dirty_tree_or_red_init_or_multi_active" },
    { "from": "repair",     "to": "plan",      "when": "baseline_clean_single_active" },
    { "from": "plan",       "to": "implement", "when": "contract_signed" },
    { "from": "plan",       "to": "escalate",  "when": "scope_ambiguous" },
    { "from": "implement",  "to": "verify",    "when": "step_complete" },
    { "from": "verify",     "to": "rollback",  "when": "boundary_violation", "kind": "rollback" },
    { "from": "rollback",   "to": "implement", "when": "tree_clean" },
    { "from": "verify",     "to": "implement", "when": "regression_or_e2e_or_edge_failure", "kind": "rollback" },
    { "from": "verify",     "to": "evaluate",  "when": "checks_ran" },
    { "from": "evaluate",   "to": "implement", "when": "verdict_revise_or_passes_below_required", "kind": "rollback" },
    { "from": "evaluate",   "to": "record",    "when": "pass_and_passes_at_or_above_required" },
    { "from": "evaluate",   "to": "escalate",  "when": "max_rounds_or_hard_stop" },
    { "from": "record",     "to": "push",      "when": "always" },
    { "from": "push",       "to": "open-pr",   "when": "always" },
    { "from": "open-pr",    "to": "pr-review", "when": "always" },
    { "from": "pr-review",  "to": "escalate",  "when": "findings_present_and_max_pr_rounds", "priority": 1, "note": "checked before pr-fix; a clean review never escalates" },
    { "from": "pr-review",  "to": "pr-fix",    "when": "findings_present_and_below_max_pr_rounds", "kind": "rollback" },
    { "from": "pr-fix",     "to": "push",      "when": "fixes_committed", "kind": "rollback" },
    { "from": "pr-review",  "to": "plan",      "when": "clean_and_more_features_in_slice" },
    { "from": "pr-review",  "to": "handoff",   "when": "clean_and_slice_complete" },
    { "from": "handoff",    "to": "stop",      "when": "always" },
    { "from": "escalate",   "to": "stop",      "when": "always" }
  ]
}
END>>>

FILE: .harness/verification/roles.md
<<<BEGIN
# Roles — Separation of Duties

The single biggest reliability lever is not a smarter model; it is separating who builds
from who judges. When one agent plans, builds, and grades itself, it declares victory early.
Splitting the work into roles that hand off with evidence removes that failure. (In the
harness-engineering benchmark, one self-reviewing role scored ~1.6/5; planner+generator+
evaluator scored ~4.9/5. The roles are the difference.)

You play these roles in sequence, switching context deliberately. Announce the switch
("Now acting as Evaluator") so it is visible and you do not blur them.

## Planner
- Input: the active feature in `ROADMAP.md`, the product/architecture docs, the handoff.
- Output: a filled `sprint-contract.md` — scope, acceptance mapped to checks, the plan,
  out-of-scope list, risks. Nothing is built until the contract exists.
- Discipline: the Planner decides *what done means* before the Generator can be tempted to
  redefine it mid-build.

## Generator (maker)
- Input: the signed sprint contract.
- Output: the implementation, plus the evidence each acceptance item calls for.
- Discipline: builds only what the contract says. Discovers scope creep? Parks it, does not
  build it. Produces the evidence; does not grade it.

## Evaluator (checker)
- Input: the contract + the Generator's output + evidence. **Does not trust the Generator's
  summary — re-runs the checks: the full suite + e2e (not a subset), plus the edge-cases
  battery.**
- Output: a score against `evaluator-rubric.md`, a defect list, and a verdict: PASS or REVISE.
- Discipline: independent and adversarial-in-good-faith. Looks for the acceptance item that
  was quietly skipped, the test that asserts nothing, the "passed" with no evidence, the
  boundary violation. The Evaluator may not fix code; it reports. A vague "looks good" is a
  failed evaluation.

## Handoff rules
- Generator -> Evaluator handoff must include: what was built, the exact commands to
  reproduce evidence, and any deviation from the contract.
- Evaluator -> Generator (on REVISE) must include: specific defects, each tied to an
  acceptance item or rubric line, and the failing evidence.
- A feature is `passed` only after an Evaluator PASS with score >= threshold. The Generator
  cannot set `passed` on its own say-so.

## When roles run as one agent vs. separate agents
- Same session, sequential: acceptable for most features. Switch context explicitly; re-run
  checks with fresh eyes.
- Separate agent/loop (`loops/maker-checker-loop.md`): preferred for risky or large
  features, and for the automated loop. The checker is a different invocation so it cannot
  see the maker's rationalizations.

## Anti-patterns (an automatic REVISE)
- Grading your own work by assertion.
- "Tests pass" without showing which tests and their output.
- Marking passed to move on, intending to "come back to it."
- Evaluator softening a defect to avoid another round.
END>>>

FILE: .harness/verification/evaluator-rubric.md
<<<BEGIN
# Evaluator Rubric

Score every feature before it can be marked `passed`. Independent (Evaluator role,
`roles.md`), evidence-based, re-run rather than trusted. Threshold: **PASS requires
>= 4.0/5.0 AND zero criteria scored 1.** Anything below is REVISE with a defect list.

Score each criterion 1–5, then average.

## Criteria

**1. Acceptance completeness** — Are ALL acceptance items in the phase file met, each with
evidence?
- 5: every item met, evidence reproduced by the Evaluator.
- 3: all met but some evidence is thin or unverified.
- 1: an item is unmet or evidence is missing/assumed.

**2. Correctness** — Does it actually work: happy path, the applicable `edge-cases.md`
battery, error paths, no regressions, and (if user-facing) e2e?
- 5: happy path + applicable edge/error cases + full suite green (no regressions) + an e2e
  test of the primary flow for user-facing work, all reproduced by the Evaluator.
- 3: happy path works; edge/error cases untested, OR no e2e for a user-facing flow, OR only a
  test subset was run (regression risk).
- 1: fails on a plausible input; a regression in a COMPLETE feature; "works on my machine";
  or the e2e/edge tests are flaky, skipped, or assert nothing.

**3. Boundary & scope compliance** — Layer boundaries (`rules/layer-boundaries.md`) and
scope guard (`rules/scope-guard.md`) respected?
- 5: check-architecture passes; nothing out of scope built.
- 3: minor smell, no hard violation.
- 1: a boundary violation, or out-of-scope work shipped.

**4. Modularity** — Was this a registration, not a core edit, where MODULES.md says it
should be?
- 5: extension points used correctly; core untouched where it should be.
- 3: works but a missed chance to use a registry.
- 1: hard-coded into core what should have been modular.

**5. Evidence & handoff quality** — Can a cold agent reproduce the result and continue?
- 5: exact commands/artifacts recorded; state + handoff updated.
- 3: evidence present but handoff vague.
- 1: no reproducible evidence, or state not updated.

## Output format (the Evaluator writes this)
```
Feature: <id>
Scores: acceptance=_, correctness=_, boundaries=_, modularity=_, evidence=_  => avg _._
Verdict: PASS | REVISE
Defects (if REVISE):
  - [criterion] <specific defect> — <failing evidence> — <acceptance item it breaks>
```

## Notes
- Grade what you can reproduce, not what the Generator claims. Re-run the commands — including
  the **full** suite (not a subset) and, for user-facing work, the **e2e** test.
- A single criterion at 1 blocks PASS even if the average clears 4.0 — a missing acceptance
  item, a boundary violation, a regression, or a missing/flaky e2e on a user-facing flow is
  disqualifying.
- Probe the `edge-cases.md` categories the Generator skipped; a plausible failing input there
  is a correctness defect, not a nitpick.
- Record the scored block in `CHANGELOG.md` as part of the evidence.
END>>>

FILE: .harness/verification/acceptance-evidence.md
<<<BEGIN
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
END>>>

FILE: .harness/verification/edge-cases.md
<<<BEGIN
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
END>>>

FILE: .harness/verification/sprint-contract.md
<<<BEGIN
# Sprint Contract — <FID>: <feature name>

Feature: <FID> — <name>
Phase: <phase number + name>
Date: <YYYY-MM-DD>

> The Planner fills this before the Maker builds. Copy this template per feature. Nothing is
> built until the contract exists and its acceptance maps to concrete checks.

## 1. Scope & Acceptance Criteria
- [ ] <acceptance item 1> — <the exact check/evidence that proves it>
- [ ] <acceptance item 2> — <check/evidence>
- [ ] <acceptance item 3> — <check/evidence>
- [ ] Boundary invariants: obeys `rules/layer-boundaries.md` (check-architecture passes).
- [ ] Edge/error cases from §2 covered by tests.
- [ ] E2E: the primary user flow passes end-to-end (or "N/A — not user-facing" with why).
- [ ] No regressions: the FULL verify (typecheck + lint + full tests + check-architecture +
      e2e) passes with zero errors.

## 2. Edge cases & failure paths (from `verification/edge-cases.md`)
List each applicable category and the concrete test that covers it; mark the rest N/A with a
word on why. An unconsidered applicable category is an incomplete contract.
- <category> -> <test that covers it>
- <category> -> <test>
- N/A: <categories that don't apply and why>

## 3. E2E scenario(s)
<the user flow(s) an e2e test will drive through the real stack, incl. the error/edge flow
(e.g. unauthorized, not-found, empty). Or "N/A — not user-facing" + reason.>

## 4. Plan (thinnest vertical slice)
<the smallest demonstrable steps, in order>

## 5. Out of scope (parked, not built)
<anything tempting that belongs to a later feature/phase — record it, don't build it>

## 6. New dependencies (with justification)
<none, or: dep — why the active feature needs it>

## 7. Risks
<what could break; the edge/error paths the Checker should probe>
END>>>

FILE: .harness/rules/conventions.md
<<<BEGIN
# Conventions

Naming, structure, git, and session hygiene. Small rules that keep the harness legible
across many sessions and agents.

## Ids
Stable, opaque, type-prefixed and immutable once assigned (define the prefixes for your
domain in `architecture/DATA_MODEL.md`). Used identically in DB, API, URLs, logs, and AI
references. Feature ids in the tracking system are `F001`, `F002`, … and never reused.

## Types / language
Strict mode on. No escape hatch (`any`, untyped) without a `// why:` comment. Shared domain
types live in one place and are imported everywhere else; never redefine a model type in a
consumer. Prefer explicit return types on exported functions.

## Files & folders
Follow `architecture/ARCHITECTURE.md` §repository shape. One module per domain area.
Colocate unit/integration tests with code. No file over ~400 lines without a reason.

## Testing
- Unit/integration tests colocated (`*.test.*`); **e2e** tests in a top-level `e2e/`
  directory, named for the flow they drive. Tag the critical ones `@smoke`.
- Every feature covers the applicable `verification/edge-cases.md` battery; user-facing
  features add at least one e2e flow (`verification/acceptance-evidence.md`).
- Tests assert real behavior — no `assert true`, no test edited to pass.
- **Flaky is broken.** A test that isn't deterministic is fixed at the root, not retried or
  quarantined (`loops/failure-modes.md`).

## Git
- One feature per branch: `feat/<feature-id>` matching the `id` in `ROADMAP.md`. For
  harness-only tooling/docs not tied to a ROADMAP feature id, use a descriptive
  `docs/<slug>` or `chore/<slug>` branch instead of forcing a fake `feat/<FID>` — the same
  PR-review-loop discipline still applies.
- Conventional commits: `feat(scope): add X`, `fix(scope): stop Y`. Reference the feature id
  in the body.
- Commit only when the FULL suite is green (not a subset) and the step has evidence. No "wip"
  on main.
- Never commit secrets, `.env`, or generated artifacts.
- After a feature passes maker-checker: push the branch, open a PR (reuse if one is already
  open for it — never open a second), review it, fix findings, and repeat until clean before
  starting the next feature. See `loops/pr-review-loop.md`.

## Evidence discipline
A feature is `passed` only with recorded evidence in `CHANGELOG.md`: the exact command, its
output (or a screenshot path under `.harness/evidence/`), or a test id. "Looks right" is not
evidence. See `verification/acceptance-evidence.md`.

## Logging
Structured logs (json) with `level`, `event`, `correlationId`, and relevant ids. Log at:
process start, each layer boundary crossing (API in/out, job start/end), and every caught
error with cause. See `scripts/SCRIPTS.md` → logger contract.

## Session hygiene (do this before you stop, every time)
1. Update `ROADMAP.md` (status + evidence).
2. Append a dated entry to `CHANGELOG.md`.
3. Rewrite `PROJECT_STATE.md` for a cold reader.
4. Run `state/clean-state-checklist.md`. Leave the tree clean.
5. Commit with the feature id.
6. If the feature (or harness-only change) just went complete: push, open/reuse the PR,
   review it, and fix findings until clean (`loops/pr-review-loop.md`).

## Comments & docs
Comment *why*, not *what*. Update the affected `.harness` doc in the same change that makes
it stale (e.g. new endpoint -> update API_SURFACE.md). Stale docs are worse than none.

## Definition of "modular"
Before adding a capability, check `architecture/MODULES.md`: can this be a registration
instead of a core edit? If yes, do that. If it forces a core change, either the abstraction
is missing (add it) or the change is genuinely core (justify it in the sprint contract).
END>>>

FILE: .harness/rules/scope-guard.md
<<<BEGIN
# Scope Guard

What is **off-limits right now**. Scope creep is the most common agent failure; this file is
the leash. The active phase is whatever `PROJECT_STATE.md` says. Building ahead of it is a
defect, not initiative. Phases are gated (ROADMAP.md order); a phase's features may not start
until the previous phase's completion criteria pass.

## Current phase: <<FILL: e.g. Phase 01 — Foundation>>

### In scope (current phase only)
<<FILL: the features that belong to the active phase, one line each — see ROADMAP.md.>>

### Off-limits until their phase (do NOT build now)
<<FILL: for each later phase, one line naming what it owns so the agent recognizes the
temptation and parks it. Keep this list in sync with ROADMAP.md.>>

## Rules of the guard
1. If a task tempts you outside the current phase, stop. Note it in `BLOCKERS.md` (or as a
   future feature in `ROADMAP.md`) and keep going on the active feature.
2. No dependency unless the active feature needs it — record new deps in the sprint contract
   with a justification.
3. Design *for* later phases (stable ids, registries, interfaces) but *build* only the
   current phase.
4. If scope is wrong, propose an edit to this file + `ROADMAP.md` — don't silently expand.
   Record the decision in `DECISIONS.md`.
5. Don't skip a phase's completion criteria. A phase is done only when every feature is
   `COMPLETE` with evidence and the phase smoke test is green.

## Why so strict
A solid, tested foundation beats half of every phase started. Early substrate multiplies its
shakiness across everything built on top of it.
END>>>

FILE: .harness/rules/layer-boundaries.md
<<<BEGIN
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
END>>>

FILE: .harness/scripts/SCRIPTS.md
<<<BEGIN
# Script Contracts

These are **contracts, not code** (this harness ships no code). Each script is specified by
purpose, inputs, behavior, output, and exit code. The first build session implements them as
real scripts under `scripts/` at the repo root and wires them into the commands in
`CLAUDE.md`. The Evaluator verifies each implementation against its contract.

Convention for all: exit `0` = success, non-zero = failure with a human-readable reason on
stderr. Structured (json) logs on stdout where noted. No script mutates `.harness/` rule
files.

---

## init
- **Purpose**: verify a clean, reproducible baseline before any work. The "start" half of
  `state/clean-state-checklist.md`.
- **Inputs**: none (reads repo state).
- **Behavior**: check the working tree is clean (warn on a dirty tree — see
  `loops/failure-modes.md`); install deps if needed; run typecheck, lint, the FULL test suite,
  `check-architecture`, and the e2e smoke; confirm `ROADMAP.md` is well-formed with exactly
  one `IN PROGRESS` feature; print the active feature + next step from the handoff.
- **Output**: a short readiness summary.
- **Exit**: `0` if the baseline is clean and buildable; non-zero listing exactly what is not.
- **Used by**: every session start; the goal loop; the timer loop.

## check-architecture
- **Purpose**: enforce `rules/layer-boundaries.md`.
- **Inputs**: the source tree.
- **Behavior**: build/inspect the import graph and assert each rule in `layer-boundaries.md`.
- **Output**: a list of violations (file -> forbidden import -> rule number), or "clean."
- **Exit**: `0` if no violations; non-zero with the list. A non-zero result blocks marking
  any feature `passed`.
- **No-op until architecture exists**: while `rules/layer-boundaries.md` has no real rules
  (architecture is defined after the requirement), this is a permissive no-op — exit `0`,
  print "no boundaries defined yet." It becomes an enforcing gate the moment real rules are
  written. This lets the loop run on day one for any project type before its architecture is
  chosen.
- **Used by**: init; the verify node in the workflow graph; the maker-checker Checker.

## e2e
- **Purpose**: prove user-facing flows end-to-end against the real stack (UI -> API ->
  datastore -> back, or CLI -> real side effect). The evidence form in
  `verification/acceptance-evidence.md`.
- **Inputs**: a running app (or the runner boots one), seeded/deterministic test data, and a
  base URL / entrypoint.
- **Behavior**: drive the primary flow and its applicable error/edge flows (unauthorized,
  not-found, empty) the way a user/client does; assert observable outcomes, not internal call
  counts; save traces/recordings under `.harness/evidence/<feature-id>/`.
- **Output**: pass/fail per scenario + the artifact paths.
- **Exit**: `0` if all scenarios pass; non-zero with the failing scenario. A non-zero result
  blocks marking a user-facing feature `passed`.
- **Used by**: the verify node; the maker-checker Checker; the PR review (via CI); the timer
  loop (smoke subset).
- **Note**: e2e must be deterministic. A flaky e2e is a defect (`loops/failure-modes.md`), not
  evidence — no `sleep`-and-hope; await real state.

## smoke
- **Purpose**: a fast subset of `e2e` — the one or two critical paths — for the timer loop and
  quick post-change confidence.
- **Behavior**: run only the flows tagged `@smoke`; same determinism rules.
- **Exit**: `0` all green; non-zero with the failing path.
- **Used by**: the timer loop; a quick check after a risky change.

## logger (contract, not a script)
- **Purpose**: runtime observability. "If you can't see why it failed, add a log before you
  add a fix."
- **Shape**: structured json lines: `{ ts, level, event, correlationId, ...ids }`.
- **Emit at**: process start (config + versions), each layer-boundary crossing (API request
  in/out, job start/end), and every caught error with its cause and the ids involved.
- **Rule**: a correlation id flows from an API request through any job it spawns. No
  `console.log` debugging left in committed code (clean-state red flag).

## benchmark
- **Purpose**: measure whether the harness is actually helping. Compares agent runs with vs.
  without harness discipline on a fixed task set.
- **Inputs**: a task set (start with the first slice's features) and a mode flag
  (`--with-harness` / `--baseline`).
- **Behavior**: run the task set, then score results against each feature's acceptance + the
  evaluator rubric; count features that actually pass and boundary violations introduced.
- **Output**: a table: features attempted, passed-with-evidence, violations, rounds used.
- **Exit**: `0` when the run completes (pass/fail is in the report, not the exit code).
- **Used by**: periodic health/ablation checks, not the build loop.

## cleanup-scanner
- **Purpose**: keep quality maintainable between sessions.
- **Inputs**: the source tree.
- **Behavior**: report dead code, unused deps/exports, TODOs that imply out-of-scope work,
  files over the size guideline, and `.harness` docs that are stale relative to the code they
  describe.
- **Output**: a findings list, grouped by severity. Report-only — never auto-edits.
- **Exit**: `0` always (advisory); findings go to the timer loop's report policy.
- **Used by**: the daily timer loop.

## progress-counter
- **Purpose**: keep `PROJECT_STATE.md` progress honest.
- **Inputs**: `ROADMAP.md`.
- **Behavior**: count features by status (COMPLETE / IN PROGRESS / BLOCKED / NOT STARTED)
  from the ROADMAP checkboxes + phase files; compute Progress % = COMPLETE / total.
- **Output**: the counts + percentage, written into `PROJECT_STATE.md` "Overall Progress" and
  `ROADMAP.md` "Progress".
- **Exit**: `0` always (advisory).
- **Used by**: session-completion protocol; the timer loop.
- **Note**: until implemented, maintain the counts by hand on every status change.

---

## (optional) scheduler / agent-relay
If you automate across runtimes (`RUNTIME-CONTINUITY.md`), these two are useful:
- **scheduler**: runs the remaining ROADMAP queue one feature at a time, detects a runtime's
  session/rate limit from its output, fails over to the other runtime, and on a dual limit
  sleeps until the sooner reset then resumes. Flags: `--start=<FID> --end=<FID>`, `--dry-run`.
- **agent-relay**: launches one runtime; when it exits (e.g. on a limit) launches the other,
  looping. Pauses for a keypress before each switch so a normal quit doesn't ping-pong.

---

## Implementation order
`init` and `check-architecture` come with the first feature (the loop needs them
immediately) — `check-architecture` ships as a permissive no-op stub and gains real rules only
when `rules/layer-boundaries.md` is filled (architecture comes after the requirement). The
`e2e`/`smoke` runner is stood up with the first user-facing feature and wired into CI then —
not before it has a flow to drive. `logger` lands with the first
API/worker code. `benchmark` and `cleanup-scanner` are useful once there is enough code to
measure — implement them by the end of the first phase, not before an active feature needs
them (scope-guard).
END>>>

FILE: .harness/state/clean-state-checklist.md
<<<BEGIN
# Clean-State Checklist

Run before you stop and before you start (init verifies the "start" half). A dirty state is
how the next session loses hours. Tick every box.

## Before starting work
- [ ] `git status` is clean, or the only changes are ones you understand from the handoff.
- [ ] `init` runs green (build + boundary check). If not, fixing it IS your first task.
- [ ] `ROADMAP.md` has exactly one `IN PROGRESS` feature and it matches `PROJECT_STATE.md`.
- [ ] You have read the sprint contract for the active feature.

## Before stopping work
- [ ] Code compiles: typecheck passes.
- [ ] lint passes with no new warnings.
- [ ] The FULL test suite passes (not just this feature's tests) — no regressions.
- [ ] New feature has tests, including the applicable `verification/edge-cases.md` battery.
- [ ] E2E passes for any user-facing flow (or the contract records "N/A — not user-facing").
- [ ] check-architecture passes — no layer-boundary violations (`rules/layer-boundaries.md`).
- [ ] No secret / `.env` / generated artifact staged or committed.
- [ ] Evidence for any status change is recorded in `CHANGELOG.md`.
- [ ] `ROADMAP.md` status + evidence updated.
- [ ] `PROJECT_STATE.md` rewritten for a cold reader (active feature + next steps + blockers).
- [ ] No stray files, no secrets, no `.env`, no debug logging left on.
- [ ] Committed on a `feat/<feature-id>` branch (or `docs/<slug>`/`chore/<slug>` for
      harness-only work) with a conventional message.
- [ ] Exactly one `IN PROGRESS` feature remains (or all passed and phase advanced).
- [ ] If the feature just went `COMPLETE`: branch pushed, PR opened/reused, reviewed clean —
      no unresolved findings (`loops/pr-review-loop.md`).

## Red flags that mean "not clean"
- Tests skipped or commented out to make the suite pass.
- Only a subset of tests run "to save time" — a regression can hide in the rest.
- An e2e test mocked across the boundary it claims to prove, or quarantined because it's flaky.
- A feature marked `passed` with `evidence: null`.
- More than one `IN PROGRESS` feature.
- Uncommitted changes with no handoff note.
- A TODO that silently expands scope (move it to the parking lot instead).
END>>>

FILE: .harness/RUNTIME-CONTINUITY.md
<<<BEGIN
# Runtime Continuity — failover across agent runtimes

Keep building without interruption when one agent runtime hits its usage/session limit, by
failing over to another. This works because **the harness is the source of truth, not the
conversation** — any runtime resumes from `PROJECT_STATE.md`. It applies multi-session
continuity across *tools*, not just sessions.

## The runtimes
| Runtime | Launch (in the repo) | Role |
|---|---|---|
| <<FILL: primary CLI, e.g. `claude`>> | in the repo root | Primary — where you start |
| <<FILL: failover CLI>> | in the repo root | Failover |

<<FILL: any install/auth one-liners for the failover runtime.>>

## The principle
Nothing important lives in the chat. Before a runtime stops (or when it hits a limit) it
commits its work and writes the exact next step into `CURRENT_TASK.md`. The other runtime
reads `PROJECT_STATE.md → CURRENT_TASK.md → ROADMAP.md → the active phase file`, inspects the
code (the codebase is the source of truth for what exists), and continues the one active
feature. No context is lost.

## Trigger
The active runtime reaches its usage/session limit (a rate-limit or max-session message).

## Handoff protocol (in order)
1. **Finish the current safe step** — don't stop mid-edit; get the tree compiling.
2. **Run the Session-completion protocol** (`AGENTS.md`): update `PROJECT_STATE.md`,
   `CURRENT_TASK.md` (exact next step — file + function), `ROADMAP.md`, `CHANGELOG.md`;
   open/close `BLOCKERS.md`; commit on the `feat/<FID>` branch. **Never leave the tree dirty.**
3. **Log the switch** in `RUNTIME-SWITCHES.md`.
4. **Start the other runtime** in the repo and give it the resume bootstrap below.
5. **Alternate** on each subsequent limit.

## Resume bootstrap (paste into whichever runtime you start)
> Resume this project. Read `.harness/PROJECT_STATE.md`, then `CURRENT_TASK.md`, then follow
> `.harness/AGENTS.md`. Work only the one active feature. Do NOT restart from Phase 1.

## Guardrails
- One active feature at a time (whatever `CURRENT_TASK.md` says). A switch changes *who*
  works, never *what* is worked on.
- Commit before switching; the receiving runtime trusts committed code over stale tracking
  and reconciles per `AGENTS.md`.
- If a limit hits mid-feature, `CURRENT_TASK.md` must record the exact next step so the other
  runtime continues rather than restarts.

## Platform note
If more than one machine/VM touches the repo, native build artifacts (installed dependencies)
belong to whichever platform installed last. After a cross-platform touch, reinstall/rebuild
for the current platform before running native-dependent tools. Treat any uncommitted change
you find in the tree as something to inspect, not assume.
END>>>

FILE: .harness/architecture/decisions/ADR-template.md
<<<BEGIN
# ADR-XXXX: <title>

- **Status**: Proposed | Accepted | Superseded by ADR-YYYY
- **Date**: <YYYY-MM-DD>

## Context
<the forces at play; what problem this decides>

## Decision
<the choice made, stated plainly>

## Consequences
<what becomes easier, what becomes harder, what is now off-limits>

## Alternatives considered
<what else was on the table and why it lost>
END>>>

═══════════════════════════════════════════════════════════════════════════════════════
                          TRACKING SYSTEM (skeletons — start empty)
═══════════════════════════════════════════════════════════════════════════════════════

FILE: .harness/PROJECT_STATE.md
<<<BEGIN
# PROJECT STATE — MASTER FILE

> Read this first, every session. Rewrite it for a cold reader before you stop.

## Where we are
- **Phase**: <<FILL: e.g. Phase 01 — Foundation>>
- **Active feature**: <<FILL: e.g. F001 — <name> (IN PROGRESS)>>
- **Overall progress**: 0 / <<FILL: total>> features COMPLETE (0%)

## Last verified
- **Date**: <YYYY-MM-DD>
- **init**: <green | red — why>
- **Full suite + check-architecture**: <green | red — what failed>
- **E2E**: <green | red | N/A — which flows>
- **Git**: branch `<branch>`, commit `<sha>` (or `Working tree: DIRTY`)

## Next step
<<FILL: the exact next action — file + function where possible. Mirrors CURRENT_TASK.md.>>

## Open blockers
See `BLOCKERS.md`. <none | summarize the active ones>

## Notes for the next agent
<anything a cold session needs that isn't obvious from the code>
END>>>

FILE: .harness/CURRENT_TASK.md
<<<BEGIN
# CURRENT TASK

**Feature**: <<FILL: FID — name>>
**Phase**: <<FILL>>
**Status**: IN PROGRESS

## Exact next step
<<FILL: the single next action. Be concrete — file, function, the check that proves it.>>

## Acceptance (summary)
See the phase file `phases/PHASE-XX-*.md` for the full criteria and the signed
`verification/sprint-contract.md` for this feature.

## Definition of done
Every acceptance item met + evidence in `CHANGELOG.md` + Evaluator PASS + check-architecture
clean + PR reviewed clean (`AGENTS.md` → Definition of done).
END>>>

FILE: .harness/ROADMAP.md
<<<BEGIN
# ROADMAP

All features across all phases, with permanent ids and status. This is the source of truth
for **scope**. Statuses: `NOT STARTED` · `IN PROGRESS` · `BLOCKED` · `IN REVIEW` ·
`COMPLETE` · `DEPRECATED`.

**Progress**: 0 / <<FILL: total>> COMPLETE (0%)

> <<FILL: this is "the requirement." List your phases and, under each, the features with a
> permanent id (F001, F002, …), a one-line description, and a status checkbox. Each feature
> gets full acceptance criteria in its `phases/PHASE-XX-*.md`. Keep exactly one feature
> `IN PROGRESS` at a time. Example shape below — replace it.>>

## Phase 01 — <name>
- [ ] **F001** — <feature> — `NOT STARTED`
- [ ] **F002** — <feature> — `NOT STARTED`

## Phase 02 — <name>
- [ ] **F00N** — <feature> — `NOT STARTED`

<!-- … add phases until the product is covered … -->
END>>>

FILE: .harness/CHANGELOG.md
<<<BEGIN
# CHANGELOG — completed implementation, with evidence

Newest first. One entry per feature that reached `COMPLETE`. An entry is not valid without
reproducible evidence (see `verification/acceptance-evidence.md`).

## Template
```
## <YYYY-MM-DD> — <FID> <feature name> — COMPLETE
Branch/commit: <branch> @ <sha>   PR: <url>   CI: <green + link>
Evidence:
  - <exact command> -> <result / test id / artifact path>
  - full suite: <command> -> <N passed, 0 failed> (no regressions)
  - e2e: <command> -> <scenarios passed / N-A not user-facing> (trace: .harness/evidence/<FID>/)
  - edge cases: <the applicable edge-cases.md categories covered, by test>
Evaluator: acceptance=_ correctness=_ boundaries=_ modularity=_ evidence=_ => avg _._  (PASS)
Notes: <anything the next agent should know>
```

<!-- entries go below, newest first -->
END>>>

FILE: .harness/DECISIONS.md
<<<BEGIN
# DECISIONS — decision log

Indexes the architecture ADRs (`architecture/decisions/`) and records lighter decisions that
don't need a full ADR. Don't relitigate a decision here without a new one that supersedes it.

## Format
```
DEC-00N (<YYYY-MM-DD>): <decision, stated plainly>. — <why> [ADR-XXXX if applicable]
```

<!-- decisions go below -->
END>>>

FILE: .harness/BLOCKERS.md
<<<BEGIN
# BLOCKERS — what's stuck

Open blockers first. Close a blocker by moving it to Resolved with the fix + date. A parked
out-of-scope temptation (scope-guard) also lands here until it becomes a real ROADMAP feature.

## Open
```
(id | opened | feature | description | what would unblock it)
--- none ---
```

## Resolved
```
(id | resolved | how)
--- none ---
```
END>>>

FILE: .harness/RUNTIME-SWITCHES.md
<<<BEGIN
# Runtime Switch Ledger

One line per runtime failover (`RUNTIME-CONTINUITY.md`). Lets us see whether the relay runs
unattended over time.

```
(date/time | from-runtime -> to-runtime | active feature | reason | tree state at switch)
--- none yet ---
```
END>>>

═══════════════════════════════════════════════════════════════════════════════════════
                    THE REQUIREMENT (placeholders — you fill these in)
═══════════════════════════════════════════════════════════════════════════════════════

FILE: .harness/product/PRODUCT.md
<<<BEGIN
# PRODUCT — the vision

<<FILL: what this product is, for whom, and why. The problem, the core idea, the shape of the
MVP, and what makes it different. This is what the agent reads to understand *why* a feature
matters. Everything the harness builds should trace back to something here.>>
END>>>

FILE: .harness/product/PERSONAS.md
<<<BEGIN
# PERSONAS — who it's for

<<FILL: the two or three users you build for, each with their goal, their context, and the
job they hire this product to do. Keep it short; it exists to settle scope arguments.>>
END>>>

FILE: .harness/architecture/ARCHETYPES.md
<<<BEGIN
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
END>>>

FILE: .harness/architecture/ARCHITECTURE.md
<<<BEGIN
# ARCHITECTURE

> Define this AFTER you have the requirement. Start from the closest shape in `ARCHETYPES.md`
> (full-stack / DevOps-IaC / Airflow) and adapt. Not every project needs `DATA_MODEL.md` or
> `API_SURFACE.md` — delete or mark them N/A for infra/tooling repos.

<<FILL: the system shape — the layers/packages/apps, how they depend on each other (this is
what `rules/layer-boundaries.md` enforces), the repository shape, and the runtime topology.
Name the pure core that everything depends on and that depends on nothing.>>
END>>>

FILE: .harness/architecture/DATA_MODEL.md
<<<BEGIN
# DATA MODEL

> Optional by archetype (`ARCHETYPES.md`): applies to data/app and Airflow projects; a
> DevOps/IaC or pure-tooling repo may mark this "N/A — no persistent domain model."

<<FILL: the core entities, their fields, the relationships, and the **invariants** the domain
enforces (validated in the core, not in controllers/components). Define the id prefixes used by
`rules/conventions.md`.>>
END>>>

FILE: .harness/architecture/API_SURFACE.md
<<<BEGIN
# API SURFACE

> Optional by archetype (`ARCHETYPES.md`): applies when the project exposes an API/CLI
> contract. An Airflow or infra repo with no served API may mark this "N/A."

<<FILL: the endpoints/contracts the project exposes (HTTP API, CLI commands, or job
interfaces), request/response shapes, and error types. Keep this current in the same change
that adds or changes one (conventions.md).>>
END>>>

FILE: .harness/architecture/MODULES.md
<<<BEGIN
# MODULES — the extension points

<<FILL: the registries/interfaces that new variants register against instead of editing the
core (new types, importers, exporters, actions, view kinds…). This is what
evaluator-rubric.md criterion 4 (modularity) and layer-boundaries.md rule "registries, not
switches" check against. If adding a feature forces a core edit that a registry should
handle, the abstraction is wrong.>>
END>>>

FILE: .harness/phases/PHASE-01-FOUNDATION.md
<<<BEGIN
# Phase 01 — <<FILL: phase name>>

<<FILL: this is the acceptance-criteria home for the phase's features. Copy this file per
phase (PHASE-02-*.md, …). For each feature, give the full, checkable acceptance criteria the
Evaluator scores against — the same items the sprint contract maps to concrete checks.>>

## F001 — <feature name>
**Status**: NOT STARTED

### Acceptance criteria
- [ ] <criterion 1 — concrete and checkable>
- [ ] <criterion 2>
- [ ] Edge/error cases from `verification/edge-cases.md` (applicable ones) covered by tests.
- [ ] E2E: primary user flow passes end-to-end (or "N/A — not user-facing").
- [ ] Boundary invariants: obeys `rules/layer-boundaries.md` (check-architecture passes).
- [ ] Verification: the FULL verify (CLAUDE.md → Commands, incl. e2e) passes with zero errors,
      no regressions.

### Evidence expected
<what proves each criterion — command output, test id, e2e trace, screenshot path>

## Phase completion criteria
Every feature in this phase is `COMPLETE` with evidence, and the phase smoke test is green,
before Phase 02 starts.
END>>>

═══════════════════════════════════════════════════════════════════════════════════════

## After scaffolding — the fill-in order

1. `product/PRODUCT.md` + `product/PERSONAS.md` — the why.
2. Architecture — **only once you know the requirement.** Start from the closest shape in
   `architecture/ARCHETYPES.md` (full-stack / DevOps-IaC / Airflow): fill `ARCHITECTURE.md` +
   `MODULES.md` (+ `DATA_MODEL.md` / `API_SURFACE.md` only if that archetype uses them) → then
   encode the real import rules in `rules/layer-boundaries.md`, which flips check-architecture
   from no-op to enforcing. The loop can build features before this step; do it when the shape
   is actually decided, not sooner.
3. `ROADMAP.md` — the phases and features (permanent F-ids) → then the per-phase
   `phases/PHASE-XX-*.md` acceptance criteria.
4. `rules/scope-guard.md` — the in-scope / off-limits lists from the ROADMAP phases.
5. `CLAUDE.md` → Commands — your toolchain, including the `test` (full suite) and `e2e`
   commands; `AGENTS.md` → Tech stack — the locked stack.
6. First `PROJECT_STATE.md` + `CURRENT_TASK.md` + `loops/loop-state.md` — point at F001.
7. Implement `scripts/init.sh` + `scripts/check-architecture.sh` as part of F001 (the loop
   needs them immediately); stand up the `e2e`/`smoke` runner + CI with the first user-facing
   feature (`scripts/SCRIPTS.md` → e2e).

`verification/edge-cases.md`, `loops/failure-modes.md`, and `architecture/ARCHETYPES.md` are
machinery — nothing to fill; they apply / guide from feature one.

Then run the loop: read state (repair if abnormal) → sprint contract (edge cases + e2e) →
Maker → verify (full suite + e2e, regression gate) → Checker → record → PR review (CI green)
→ next feature.
