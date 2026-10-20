---
name: session-summary
description: Use at the end of a work session on a DAE feature, so the next session picks up cleanly. Triggers — "/engineer.session-summary", "wrap up the session", "write the session log", "I'm stopping for the day".
---

# session-summary

Write the per-session entry in a feature's `session-log.md` so the human can close the laptop and pick back up cleanly. The human-readable counterpart to the machine handoffs. `checkpoint: null`.

## When to use

At the end of a work session on a feature. Three boundaries reach it without the human remembering to:

- **The feature merged** — `post-merge` Step 6 auto-invokes it at autonomy `medium`/`high`.
- **The context is about to compact** — an optional `PreCompact` hook; see `${CLAUDE_PLUGIN_ROOT}/examples/pre-compact-session-summary.md`. This is the boundary where the pickup record matters most, because everything else about the session is about to be summarized away.
- **The human stops** — an optional `Stop` hook.

Both hooks are project config, not part of this skill.

It is deliberately **not** invoked at every checkpoint exit: this is a per-session record, and several entries a day makes `session-log.md` useless for the one job it has — being readable when you come back cold.

**Not for:** mid-session (nothing's wrapping up); syncing the tracker (`progress-log`); per-skill records (each skill's own handoff).

## Workflow

1. **Resolve + scope** — resolve the methodology root + manifest via `${CLAUDE_PLUGIN_ROOT}/scripts/dae_resolve.py` (see `references/resolving.md`). Scope = the feature(s) the session touched (default: current branch; multiple → an entry in each; none → nothing to log, stop).
2. **Gather** — synthesize from this session's `handoffs/*.md`, git activity on the branch, and conversation context (decisions, problems, deferrals).
3. **Append the entry** — append (never overwrite) to `features/NNN-<slug>/session-log.md`:

```markdown
## Session — <ISO date> <start>–<end>
**Current state:** <which checkpoint, one line>
### Previous tasks (done this session)
- ...
### Current task
- <in progress at session end, if any>
### Next tasks
- <concrete, actionable, ordered>
### Open questions / blockers
- <or "None">
```

Create the file with a `# Session log — <title>` heading if absent.

4. **Tear down session-end infra.** Run `${CLAUDE_PLUGIN_ROOT}/scripts/dae_infra.py teardown` (no args = all entries with effective `teardown: session-end` or `always`). Default behavior leaves entries with `teardown: leave-running` (the per-entry default and the project-wide default we ship with) untouched — emulators are expensive to start, and the user typically wants them up across sessions while working on a feature. The teardown's JSON output goes into the session log as a one-line summary.

5. **Branch cleanup if merged.** If the current branch is not `main`/`master`, run `git fetch origin --quiet` then `git merge-base --is-ancestor HEAD origin/HEAD` (fallback `origin/main`). If the branch is merged, defer to `/engineer.post-merge` (the dedicated cleanup skill) — at autonomy `high`/`medium` auto-invoke it; at `low` surface the finding. If the branch is **not** merged, do nothing — the work isn't complete yet. Record the post-merge outcome in the session log.

6. **Handoff** — emit a summary.

## Handoff

Emit per `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md`. `checkpoint: null`; `human_action_needed: no`; `recommended_next`: the first "Next task" from the entry. (session-summary is not the handoff processor, so it follows the normal contract — no exemption.)

## session-log.md vs handoffs vs progress.md

Three records, three readers: `handoffs/` = machine, per-invocation; `progress.md` = machine-derived, glanceable; `session-log.md` = human, per-session, narrative. They don't duplicate — different granularity, different reader.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/plain-prose.md`: write every artifact this skill produces to these rules
- [Foundation Design](https://www.notion.so/3585ecdee0e2811bbc67ff4913c03207) — `session-log.md` in the storage layout, the session-log ↔ handoffs distinction (Section 5)
- `engineer/scripts/dae_infra.py` — invoked here at session end
