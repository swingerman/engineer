# Parallelism — discover it at planning time, per actual work

The DAE default is one agent, one step, in sequence. But a lot of pipeline work
*decomposes*: the same operation over many independent units, or a step whose
confidence rises when several agents attack it from different angles. This file
is the reflex a skill runs **while it plans its steps** (building the Indicator-2
todo roadmap — see `progress-indicator.md`): look at the work in front of you and
decide whether *this* feature's work is parallel, then go parallel only when it
actually is.

**Never hardcode "this step fans out."** Re-derive it from the real work each
run. The same step is sequential for a 2-file feature and a workflow for a
200-file one.

Shapes use the standard names from
`${CLAUDE_PLUGIN_ROOT}/references/graph-shapes.md` (Chain, Branch, Fan-out,
Fan-in, Diamond, Star, Tree, Loop, Feedback, DAG).

## The reflex — four questions per planned step

Ask these against the concrete work (this feature's files / ACs / mutants, this
project's features / modules), not the step in the abstract:

1. **Decompose?** Does the work split into N independent units with no
   data-dependency between them? (changed files, ACs, surviving mutants,
   discovered features, repo modules) → **Fan-out**, or **Diamond** when the
   results are merged.
2. **Quality pattern?** Would a repeatable multi-agent shape raise confidence
   here? The options are a **Star** (adversarial-verify: skeptics try to refute
   each finding), a **Tree** (judge-panel: draft from N angles, score,
   synthesize), or a **Loop** / **Feedback** (repeat rounds until a target or
   until there is nothing left; it must declare a cap, see the loop rule below).
3. **Independent siblings?** Are downstream steps/tasks mutually independent and
   runnable at once? (N specs = N TDD cycles; several features dispatchable
   together) That is parallel *step* execution, not just parallel items.
4. **Hardcoded or model?** For each node of the shape you picked, is its edge
   hardcoded or handed to a model? Name the **one dynamic slot** (the router,
   the count, the synthesis, the critic, the `again?` check) and hardcode the
   rest. A shape where every edge is a model decision is not a shape anyone can
   predict.

If 1–3 do not fire → sequential (a **Chain**), silently. No offer, no noise.

## Two rules the reflex enforces

- **Loop rule.** Every Loop or Feedback shape declares a `max_rounds` cap and a
  no-progress stop (two consecutive rounds with the same outcome). A loop
  without both fails the reflex, the same way an unbounded fan-out would. Loops
  with a human in them are exempt, because the human is the cap.
- **Outside evidence.** Something outside a Fan-out, Diamond, Star or Tree must
  check its results: `verified_by: tool` or `verified_by: human`. A plan whose
  only check of a fan-out is another agent inside the same fan-out fails the
  reflex. Name the outside check (the test run, the script, the human gate)
  when you pick the shape.

Full statement of both: `${CLAUDE_PLUGIN_ROOT}/references/graph-shapes.md`.

## Skip-gate — stay sequential, say nothing

- Scalar work, or N < 2.
- Coding units that share context (the same module, the same types, one
  refactor). Multi-agent runs cost roughly 15× the tokens of a single chat, and
  Anthropic's research-system write-up names shared-context coding as a poor
  fit for them. Parallel *read-only review* of the same code is the exception:
  the lenses don't share state.
- Units depend on each other (each needs the previous result).
- A human sign-off splits the units (AC approval, plan architecture confirm,
  charter sign-off). Workflows take **no mid-run human input**, so any fan-out
  must sit entirely on the machine side of the gate — fan out *up to* the gate,
  stop, resume after.
- The units are cheaper to just do than to dispatch (a few tiny reads, a few
  lines of change).

## Tier — how to go parallel

| Tier | Substrate | When |
|---|---|---|
| 1 | one agent, sequential | skip-gate hit (the default) |
| 2 | several Agent-tool calls **in one message** (a plugin role agent from `agents/` when one fits — see `host-capabilities.md`) | small fixed fan-out (≈2–6), results fit context |
| 3 | the **Workflow tool** (dynamic workflow) | large N, or a quality shape (Star / Tree / Loop) |

Workflows are paid-plan + version-gated and may be off. Unavailable → **degrade**
3→2→1; never hard-fail on the substrate. Parallel agents that **edit files in
place** need `isolation: "worktree"` to avoid clobbering each other; read-only
reviewers don't.

### Fork safety

A **fork** (a context-inheriting subagent) re-wakes every time one of its
detached children completes — which makes two things dangerous:

- **Never launch detached/background runs inside a fork.** A fork that fires a
  detached `Bash` run (or a background task) re-wakes on each child completion and
  can self-perpetuate. One Playwright-capture fork looped this way, burned ~300k
  tokens, and clobbered committed screenshots. Inside a fork, run such work
  **foreground** — or don't fork.
- **Browser / iterative-capture work is not fork-safe.** Screenshot loops,
  browser drives, and anything that re-runs on its own output belong in a **plain
  subagent (default isolation)** or a **workflow** — never a fork. See
  `handoff-dispatch.md`.

## Offer — the engineer decides, keyed to autonomy

Parallelism is a *presentation*, not a silent choice — surface it, default to the
recommendation, honour the feature's `autonomy_level` (the source of truth and
the "don't bounce mechanical decisions to the human" principle both live in
`handoff-dispatch.md`):

| `autonomy_level` | behaviour |
|---|---|
| `low` | offer the pick with the recommended tier as default; wait for the nod |
| `medium` | offer as a one-liner with the default; proceed unless redirected |
| `high` | auto-pick the recommendation and *report* it ("fanned out over 14 files via workflow") |

One-line offer shape:

    This step decomposes over <N> <units> (<why independent>).
    Recommended: <tier> — est. <N> agents × <read set per agent>.
    [proceed] / sequential / parallel / workflow

The cost line isn't decoration. Multi-agent runs cost roughly 15× the tokens of
a single chat, so the human should see what they're buying. Each returned
result also lands in the orchestrator's context. The reporting contract in
`handoff-dispatch.md` caps every reply at ~1,500 tokens so a fan-out can't
flood it.

## Common shapes — priors, not a contract

Recognise these fast — but the trigger is always the real work, and any of them
stays sequential when this feature's N is small:

| Where | Decomposes over | Shape (DAE name) | Tier | Model class |
|---|---|---|---|---|
| onboard — discover features | modules × discovery angles | Diamond (multi-modal sweep → dedup) | 3 | economy |
| refine — review changed code | files × dimensions | Diamond → Star (adversarial charter-verify) | 3 | inherit |
| harden (feature + fix mode) — mutation | surviving mutants | Loop (loop-until-score; cap = survivors at start) | 3 | inherit |
| harden — introversion confirm | flagged vacuous tests | Fan-out → Star | 2/3 | economy |
| harden — formal checks | selected TLA+/Lean targets | Diamond, plain subagents (not fork-safe) | 3 | frontier |
| consistency-check `--project` | features | Fan-out (judgment checks) | 3 | economy |
| progress-log `--project` | features → tracker | Fan-out | 2/3 | economy |
| plan — propose architecture | design angles (MVP / risk / reuse-first) | Tree (judge-panel → human picks) | 2 | inherit |
| discover-acs (reverse-eng) | the four passes over existing material | Diamond (multi-modal sweep → dedup) | 2 | inherit |
| fix — investigate | top-3 candidate features | Fan-out (parallel prime-context) | 2 | economy |
| **CP2/CP4 exit — review panel** | the two standing roles | Star (adviser + advocate, concurrent) | 2 | frontier / inherit |
| **CP5 exit — gauntlet** | rounds against a declared bar | Feedback (builder ↔ fresh critic, cap 5) | 3 | inherit / frontier |
| **a whole feature — `/engineer.run`** | the checkpoints between human gates | DAG of segments; the coordinator is the dynamic slot | 1–3 per segment | inherit |

**Tier** above is the parallelism substrate (1/2/3); **Model class** is a
different axis — `economy` / `inherit` / `frontier`, never a product name, because
model names get deprecated and classes do not. The **gauntlet** is the other
fixed-composition entry (a builder and a fresh critic, alternating rather than
concurrent): see `${CLAUDE_PLUGIN_ROOT}/references/gauntlet.md`. It is a prior, not a contract:
re-derive it per dispatch from the actual charge, and resolve the class against
the Agent tool's live `model` enum, per
`${CLAUDE_PLUGIN_ROOT}/references/model-classes.md`. The review panel is the one fixed-composition
entry: see `${CLAUDE_PLUGIN_ROOT}/references/review-panel.md`.

Tier-3 workflow scripts stay small and pass the item list as `args`; keep the
script next to the skill that uses it.

## Why here — the planning phase

Discovery belongs at planning time because that's when the work's shape is first
known: the todo roadmap already enumerates the steps, and for a set-valued step
the skill already holds the item list. Assessing parallelism there costs nothing
extra and keeps the decision next to the plan it changes.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/graph-shapes.md` — the shape catalogue, the loop rule, outside evidence, the pipeline walked shape by shape
- `${CLAUDE_PLUGIN_ROOT}/references/coordinator.md` — `/engineer.run`, which applies this reflex across a whole feature
- `${CLAUDE_PLUGIN_ROOT}/references/progress-indicator.md` — Indicator 2, where this reflex fires
- `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md` — autonomy source; cloud-vs-local channel for a dispatched agent
- The Claude Code dynamic-workflows docs — the Tier-3 substrate
