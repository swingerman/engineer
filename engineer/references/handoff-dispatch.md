# Handoff Dispatch — when to keep going, when to stop

After a skill writes its handoff, the next checkpoint often needs a **fresh agent** (e.g. charter §6 separates implementer from verifier). The fresh-agent rule is structural — it means "a different agent context than the one that just ran" — and a **subagent dispatched via the Agent tool satisfies it**, just as well as a brand-new human-initiated session.

**Do not bounce mechanical dispatch decisions back to the human.** The pause where the implementing agent says "want me to dispatch the verify subagent?" is friction with no upside — the user will say yes every time, and the answer was deterministic from the handoff.

## The rule

**Stop ONLY when:**

1. Something is **genuinely ambiguous** about what to do next (multiple plausible directions, no clear winner).
2. The charter or feature explicitly requires **human verification or acceptance** at this checkpoint (e.g. a `plan_status: pending-approval` gate; a high-risk migration the charter flags).
3. The active feature's effective `autonomy_level` is **`low`** — the lowest level is explicitly the "ask first" mode.

**Otherwise: DISPATCH** the next agent automatically via the Agent tool. Brief it with the feature slug, the relevant handoff, and the next-checkpoint instructions.

## Autonomy decision table

| Effective `autonomy_level` | Default dispatch behavior |
|---|---|
| `low` | Confirm with the user before dispatching ("ready to spawn the verify subagent?"). One-line confirm, then go. |
| `medium` | Auto-dispatch. Surface the dispatch in a single line ("dispatching verify subagent for `<feature>`"); no question. |
| `high` | Auto-dispatch silently. Report only the subagent's outcome. |

Effective autonomy = `feature.md` `autonomy_level`, capped by `manifest.autonomy.path_overrides` for the feature's path. Read this once during the skill's resolve step; it's already loaded.

## External-write gate — some actions are never auto

`autonomy_level` governs *dispatching the next checkpoint*. It does NOT authorize
**outward-facing or self-modifying writes**. These require **explicit human
authorization every time, regardless of autonomy** — even at `high`:

- pushing to a protected/default branch (`main`/`master`), or force-pushing;
- creating/merging a PR, or posting a PR/issue comment;
- self-modifying agent config (`.claude/settings.json`, hooks, this manifest);
- any write to a live external system (prod, tracker rows a human owns, deploys).

At `high` autonomy a vague prompt ("pick up where we left off", "merged") must
**not** be read as consent to any of the above. Do the local pipeline work
automatically; for an external/self write, ask first with the specific action
named. (This is why the auto-mode safety classifier kept blocking these — the
skill should ask proactively instead of relying on the net.)

**The one carve-out — `verify: auto` merge.** A feature whose
`gate_profile.verify` is `auto` may **auto-merge its own PR without asking** —
but only when `${CLAUDE_PLUGIN_ROOT}/scripts/dae_mergeready.py <feature-dir>`
returns `ready: true` (fail-closed) and no guardrail forces human (opt-in,
`autonomy_level` not `low`, no uncovered qualitative surface, no charter-flagged
path, default `validation_method` — see `${CLAUDE_PLUGIN_ROOT}/references/gate-profile.md`).
It posts the readiness bar as the PR comment. This is the **sole** exception to
"creating/merging a PR always asks"; every other item above — pushing to
main, force-push, self-modifying config, deploys, other external writes — still
always asks, even under `verify: auto`.

## Channel — cloud-first, local fallback

The autonomy table decides *whether* to dispatch. This decides *where*. Once a DISPATCH decision is made, prefer a **cloud agent** and fall back to a **local subagent** only when the environment requires it.

1. Run `${CLAUDE_PLUGIN_ROOT}/scripts/dae_delegable.py <feature-dir>` → `{channel, cloud_blockers}`.
2. **`channel: cloud`** and the project is remote-ready (`manifest.remote.ready: true`) → dispatch to the cloud: call the **Agent tool with `isolation: "remote"`** (fresh clone, runs in the background, opens a `claude/*` PR; its result returns to this pipeline). Use the same brief template below.
   - If `isolation: "remote"` is unavailable in this environment **and** the feature is `assignee: cloud` with a routine configured, fire the routine instead via the **`RemoteTrigger` `run` action** (fire-and-forget; the human reviews in claude.ai/code). Otherwise fall back to local.
3. **`channel: local`** (any blocker), or `manifest.remote.ready` is false/unset → dispatch a **local** subagent via the Agent tool (default isolation). The `cloud_blockers` list says why; surface it in one line at `medium`/`high`.

`assignee: cloud` is a *request*, not an override — a hard blocker (stdio MCP, unpushed branch, local infra) still routes local. `dae_delegable.py` is the source of truth; never hand-wave past a blocker.

When a cloud dispatch opens a PR, record `cloud_session_url` and the PR link in the feature's handoff so `progress-log` projects them and `next` can show the feature as **DISPATCHED — awaiting cloud PR**.

## Special case — the next agent needs infrastructure (emulators, drivers, services)

If the next checkpoint's work needs running infrastructure, **do not** write a "start this manually" command and stop. Instead:

1. Read `manifest.yml`'s `infra:` section.
2. Call `${CLAUDE_PLUGIN_ROOT}/scripts/dae_infra.py ensure <name> [<name> …]` for each dependency.
3. If `ensure` returns success → proceed with the dispatch.
4. If `ensure` returns a `start-failed` failure → surface the structured diagnosis to the user (`diagnosis`, `detail`, `suggested_fix`) and stop. This is one of the legitimate stop reasons.
5. If the required infra is not declared in `manifest.yml` → stop with: "declare `<name>` in manifest.yml `infra:` section per the DAE infra schema, or pre-start the service." Do NOT fall back to grep-the-README reasoning; the declaration discipline is the contract.

The old escape "I can't access live emulators / prod creds / hardware" is now narrowly: the script tried, the script failed, here's exactly what failed and how to fix it.

## Fork safety

When dispatching via the Agent tool, a **fork** (context-inheriting subagent) is
NOT a safe vehicle for browser or iterative-capture work (screenshots, Playwright
drives, anything that re-runs on its own output): a fork re-wakes on every
detached-child completion and can self-perpetuate (a capture fork once looped
~300k tokens and clobbered committed screenshots). Route such work to a **plain
subagent (default isolation)** or a **workflow**, and never launch detached/
background Bash runs inside a fork. See `${CLAUDE_PLUGIN_ROOT}/references/parallelism.md` (Fork safety).

## Subagent brief template

When you do dispatch via the Agent tool, use this shape:

```
description: <Checkpoint N for <feature-slug>>
model: <economy | inherit | frontier — a class, not a product name;
        resolve against the Agent tool's live `model` enum at dispatch time.
        See references/model-classes.md>
prompt:
  You are running Checkpoint <N> for feature <slug> in a DAE methodology project.

  Context:
  - Working dir: <abs path>
  - Branch: <branch>
  - Previous checkpoint's handoff: <path to handoff .md>
  - Feature artifacts: features/<slug>/{feature.md, acs.md, spec.md, plan.md, progress.md}

  Your job: <one-paragraph charge from the next-checkpoint's skill description>.

  Constraints:
  - You are the fresh agent the charter §6 calls for; do NOT relax independence.
  - Honour the effective autonomy_level: <low|medium|high>.
  - Code lookup: <LSP is available — use it for find-references / definitions / call-hierarchy | LSP is unavailable — fall back to grep + Read>. See references/code-lookup.md.

  Report on completion: <what the parent skill expects back>.
  <the reporting contract — see below>
```

The brief is **self-contained** — the subagent doesn't see the parent skill's conversation.

**`model:`** carries a **class**, never a product name — model names are retired
and replaced, and one pinned into a skill becomes a silent bug the day it is
deprecated. Defaults to `inherit` (omit the field). Use `economy` when the
charge is mechanical (a fixed rubric, a schema check, codegen from an IR, a
script wrapper) and `frontier` for a bounded one-shot judgment call. Resolve the
class to an actual model by reading the Agent tool's own `model` enum at dispatch
time — that list is current by construction. Decide the class per dispatch from
the actual charge; never hardcode either a class or a model into a skill. Full
rules: `${CLAUDE_PLUGIN_ROOT}/references/model-classes.md`.

## The reporting contract — every dispatch, no exceptions

A dispatched agent's plain text is a **return value**, not a message to a human,
and depending on the channel it may be invisible outside its own session. Agents
have gone idle with completed findings stranded. Close the brief with the
delivery instruction spelled out:

    Your final text is the return value, not a message to a human. It is not
    visible to the parent session unless you deliver it through the channel
    named here: <SendMessage to "<parent-id>" | your final text (Agent-tool
    subagent)>. Deliver before you finish, even if brief or partial. If you did
    not actually do the work described, say so plainly rather than
    reconstructing something plausible — downstream artifacts will be edited
    based on what you report.

The last sentence matters as much as the first: a plausible reconstruction from
an agent that never ran the investigation is worse than an empty report, because
it is acted on.

## What this rule replaces

Previously, every implementing skill ended with a passive handoff and the human had to manually invoke the next checkpoint. That bounced ten mechanical decisions per feature back to the human. The rule above keeps the human in the loop for the decisions that matter (ambiguity, charter-required acceptance, low autonomy) and removes them from the ones that don't.

## References

- `engineer/scripts/dae_infra.py` — probe + auto-start + teardown of declared infra
