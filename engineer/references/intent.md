# Intent — the front of the artifact chain

**Intent** is the originator's captured need, made *human-readable and
machine-actionable*, before any spec exists. It is the first link in the chain
that every later artifact derives from: **intent → ACs → spec → plan → code →
verification**. DAE has always had this; this reference names it and makes it an
async front door.

Borrowed vocabulary from Anthropic's AI-native SDLC playbook (which formalizes an
`intent.md`). DAE is a stricter implementation of that playbook — see the mapping
below — so "speaking intent" is about **interop and legibility**, not a new
process.

## Who writes it — the originator

Anyone. A customer filing a bug, a PM with a feature idea, a developer capturing
a process improvement. The originator does not have to be a specialist; they drop
their need, and DAE's disciplined pipeline takes it from there. The originator
reviews what the agent synthesized and corrects it — intent is a two-way draft,
not a handoff form.

## Where intent lives in DAE (three grades of the same thing)

| grade | artifact | who | when |
|---|---|---|---|
| **raw capture** | one line in `.engineer/inbox.md`, or a tracker row with no slug (`Type: bug\|idea\|task`, `Status: Inbox`) | anyone, zero ceremony | a thought worth not losing |
| **synthesized intent** | the `discuss` handoff (features) · `fix` Step 1 capture (bugs) · an `intent.md` an originator wrote | agent-interview or originator-authored | when it's worth pursuing |
| **contract** | `feature.md` (Ready) · the `fix` defect record | after triage/sign-off | entering the pipeline |

`next` triages raw captures into the synthesized grade. The synthesized grade is
what an agent can act on without the originator in the room.

## The async front door — an `intent.md` you can drop

An originator who doesn't want an interactive `discuss` session can **write an
`intent.md`** (free prose: what they need, why, any constraints) and hand it in.
DAE accepts it as a seed:

- **feature intent** → `discuss` / `feature-init` read the `intent.md` instead of
  interviewing, confirm the synthesis with the originator, and proceed (or route
  to the prototype-first path — see `references/two-paths.md`).
- **bug intent** → `/engineer.fix` reads it as the Step 1 capture.

This is the same "originator drops their thoughts" flow the playbook describes —
DAE just runs it through triage + the disciplined chain rather than
auto-generating a spec on commit.

## Maintenance — intent generated from a signal

The aspirational end of the SDLC: no human in the loop at the *start*. A trigger
(a Sentry alert, a Slack message, a CI failure, a schedule) invokes `/engineer.fix`
with the signal; `fix` **synthesizes the bug intent from the logs/ticket** in
Step 1 and drives the fix pipeline, surfacing to a human only at the review gates
its autonomy/criticality demand. Wire the trigger with the `schedule` skill
(cron routines) or an external alert → `claude -p "/engineer.fix <signal>"`. See
the `fix` skill's "Maintenance auto-invocation" note.

## The full DAE ↔ AI-native-SDLC mapping (Rosetta)

DAE covers the whole life cycle, more strictly:

| AI-native SDLC stage / artifact | DAE / `engineer` |
|---|---|
| **intent.md** (interview the originator) | `inbox.md` capture + `discuss` (interview) / async `intent.md` → `feature.md` |
| backlog + agent triage | `roadmap` (horizon/priority/area) + `next` |
| **spec.md** (auto from intent) | `discover-acs` (ACs) + `atdd` (Gherkin + *executable* pipeline) |
| **plan.md** (interrogate, handoff-complete) | `plan` + review-panel + `handoff-summary` |
| build (auto mode, worktrees, subagents, hooks) | CP5 `atdd-team` (parallel subagents, worktrees, autonomy-dispatch) + deterministic gates |
| test (lint/e2e/evals) | CP6 refine + CP7 verify (arch-check, CRAP, mutation, gauntlet) + plugin eval |
| deploy (PR, async Claude review, gates) | `verify: auto` + `dae_mergeready` + `post-merge` + `/code-review` + `/security-review` |
| maintenance (auto-invoke, self-generated intent) | `fix` (+ "why didn't we catch it" loop) + trigger→intent (this doc) |
| artifact chain, versioned + governed | handoffs (versioned transitions) + tracker + ontology; `dae_metrics` (DORA/governance) |

Where DAE goes beyond the playbook: the charter + `arch-check`, deterministic
ledger gates, `gate_profile`/`verify: auto` (human-at-the-ends, formalized), the
gauntlet, and **two paths** (spec-first + prototype-first).

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/discuss/SKILL.md` — synthesized feature intent (interview or `intent.md`)
- `${CLAUDE_PLUGIN_ROOT}/skills/fix/SKILL.md` — bug intent + maintenance auto-invocation
- `${CLAUDE_PLUGIN_ROOT}/references/two-paths.md` — where feature intent forks spec-first vs prototype-first
- `${CLAUDE_PLUGIN_ROOT}/references/tracker.md` — raw-capture/inbox + `next` triage
