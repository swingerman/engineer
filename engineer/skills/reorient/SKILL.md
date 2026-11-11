---
name: reorient
description: Use mid-task when the working thread is lost — after a context compaction, a long agent run, or coming back to a feature unsure of the role, the current checkpoint, or the next action. Triggers — "/engineer.reorient", "reorient", "re-anchor", "what should I be doing right now", "I lost track", "where was I".
---

# reorient

Restore the working contract mid-task. After a context compaction or a long
run, an agent loses role identity, invents constraints that do not exist, skips
required steps, and loses the task thread. `reorient` reloads the durable state
that should have survived — the discipline contract first, the task pointer
second.

Read-only and advisory. It changes nothing, produces no artifact, and emits
**no handoff** — like `next`, the orientation block is the whole output; a
handoff would only restate it. The third skill exempt from the agentic summary
contract.

`reorient` is the mid-task, feature-scoped counterpart to `next` (project-scoped,
session-start).

## When to use

- Right after a context compaction (a `SessionStart` hook can auto-invoke it).
- Mid-task, when unsure of the role, the current checkpoint, or the next action.
- Returning to a feature after an interruption.

**Not for:** session-start "what should I pick up across the project" (`next`);
loading a feature not yet started (`prime-context`); validating artifacts
(`consistency-check`).

## Workflow

### Step 1 — Resolve and locate

Resolve the methodology root + manifest via
`${CLAUDE_PLUGIN_ROOT}/scripts/dae_resolve.py` (see `references/resolving.md`).
Locate the feature (slug arg or branch name). If no feature is in scope, say so
and suggest `next` instead. **Layout disambiguation:** if the project has BOTH a
`features/NNN-*/` and a `specs/NNN-*/` tree (a speckit migration in progress),
say which one holds this feature; and if more than one acceptance-IR convention
exists (`features/NNN/.build/spec.json` vs an `acceptance-pipeline/ir/` per-GWT
layout), name the one in force — so re-anchoring doesn't rediscover the split.
(`speckit-consolidate` unifies it.)

### Step 2 — Reload the discipline contract, then the task pointer

Read, read-only, in this order:

1. **Role + autonomy** — `CHARTER.md` + manifest: the autonomy level in force,
   and what the agent may and may not decide. Counters invented constraints.
2. **Current checkpoint + exit criteria** — the Checkpoint Exit Contract
   (Foundation Design Section 8) for the checkpoint `progress.md` shows in
   progress: its goal, its exit criteria, and which are already met. Run
   `${CLAUDE_PLUGIN_ROOT}/scripts/dae_progress.py <feature-dir>` and show its
   breadcrumb — the same pipeline-position line the checkpoint skills surface
   at Step 0.
3. **Non-negotiables** — verification independence and charter-mandated
   mutation: steps that must not be skipped regardless of cost. The cost of a
   step is never a reason to skip it.
4. **Current task + next action** — the `progress.md` CURRENT header.
5. **Feature contract** — `feature.md` outcome + scope. Counters goal drift.

Also run `${CLAUDE_PLUGIN_ROOT}/scripts/dae_handoff.py <feature-dir>` — report any
checkpoint marked done without a complete handoff as a discipline gap.

**Done + unmerged.** A feature on its branch with `feature.md status: done` and no merged PR has its ship commit but isn't shipped. Show it as "awaiting merge" (next action: review/merge the PR), never as shipped.

Also run `${CLAUDE_PLUGIN_ROOT}/scripts/dae_reconcile.py <feature-dir>` (read-only):
if it reports `needs_reconcile: true`, this feature's PR is already merged (`gh`-detected —
covers squash-merge and `git.manual`) and the local state is stale. Do **not** re-anchor on
a phantom in-progress checkpoint — surface that it shipped and recommend `/engineer.post-merge`
to reconcile. `reorient` is read-only, so it never applies the flip itself.

### Step 3 — Emit the orientation block

Output one tight block, nothing else:

```
You are <role> at autonomy <level>.
Feature NNN-slug — Checkpoint N (<goal>).
Exit criteria: <m>/<n> met — unmet: <list>.
Current task: <task> -> next action: <action>.
Must not skip: <non-negotiables>.
Constraints: <charter / autonomy limits>.
```

### Step 4 — Stuck-loop detection

Before stopping, scan the feature's recent handoffs for a stuck loop. A loop is "stuck" when **three or more consecutive handoffs** from the same skill share:
- the same `status` (typically `interrupted` or `complete`-with-unmet-criteria), AND
- the same recommended-next, AND
- substantially the same `findings_summary` / failure signature (e.g. same error class, same blocker name, same infra failure type).

A stuck loop is the agent re-attempting the same operation expecting different results. nexthq saw 60+ identical ticks over 12 hours on a Functions emulator blocker — the autonomous loop never escalated to the human.

Threshold is tunable via `manifest.autonomy.stuck_loop_threshold` (default `3`).

When detected: STOP. Do not silently re-run. Emit (just this once — break the no-handoff rule) a `session-summary`-style escalation handoff that:
- Names the repeated failure signature.
- Lists the N affected handoffs by filename.
- Sets `human_action_needed: decision` and `human_action_kind: unblock-stuck-loop`.
- `recommended_next`: "human review required — N consecutive identical failures from <skill>".

The escalation handoff lives in `.engineer/handoffs/` (it's project-scope, not feature-scope progress). The human picks the unblock — a different approach, a charter amendment, an environment fix, or a deferred re-try.

### Step 5 — Stop

If Step 4 found no loop: `reorient` orients; it does not act. The human resumes the work. No handoff.

If Step 4 escalated: the escalation handoff is the output. The loop is broken — wait for the human.

## Optional: auto-invoke on compaction

A project may add a `SessionStart` hook (`source: compact`) that nudges
`/engineer.reorient` after every compaction. See
`${CLAUDE_PLUGIN_ROOT}/examples/session-start-reorient.md`. The hook is optional
project config, not part of this skill.

## References

- [Foundation Design](https://www.notion.so/3585ecdee0e2811bbc67ff4913c03207) —
  the Checkpoint Exit Contract (Section 8); agentic summary exemptions (Section 5)
- Sister skill: `next` — the project-scoped, session-start counterpart
