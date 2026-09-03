---
name: fix
description: Use to drive a bug fix from first report through close, with a "why didn't we catch it?" loop at the end. Triggers — "/engineer.fix", "a bug came in", "this is broken", "a user reported X", "there's a defect", "we have a regression", "this needs a fix", "another report", "more issues", "still failing", "validation failed again", "another bug", "next defect", "more fixes".
---

# fix

The defect unit-of-work — parallel to "feature" in the DAE pipeline. Tracks a bug from first report through a regression spec, code fix, hardening, and a structured retrospective that feeds back into the methodology.

Unlike ad-hoc fixes, the `fix` workflow enforces a regression spec that must be RED on current code before any change, and closes the loop with a "why didn't we catch it?" gap analysis tied to a closed category vocabulary. That loop is the methodology contribution: bugs become methodology feedback, not just patches.

## When to use

- A bug report arrives (user report, Sentry alert, stack trace, regression in CI).
- A defect needs a repeatable reproduction path and a tracked fix.
- A regression must be proven to stay fixed (mutation gate).

**Not for:** building a new capability (`/engineer.discuss` or `/engineer.feature-init`); adjusting an in-flight feature's scope (`/engineer.feature-edit`); reviewing recent changes without a defect (`/engineer.verify` or `/crap-analyzer`).

**Maintenance auto-invocation.** `fix` is the landing point of the SDLC's maintenance loop (`${CLAUDE_PLUGIN_ROOT}/references/intent.md`): a trigger — a Sentry/CI alert, a Slack message, or a schedule — can invoke it with no human at the start. Wire the trigger via the `schedule` skill (cron routines) or an external alert calling `claude -p "/engineer.fix <signal>"`; Step 1 synthesizes the bug intent from the signal/logs and the pipeline runs, surfacing to a human only at the review gates its `severity` + effective autonomy demand (a `critical` or user-blocking defect always confirms; low-severity internal ones can run further unattended). The external-write gate (`${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md`) still applies — a maintenance run never merges/deploys on its own unless `verify: auto` + `dae_mergeready` clear it.

## Workflow

**Infra contract.** Any step that runs tests, mutations, or the regression spec MUST first ensure required infra is up via `${CLAUDE_PLUGIN_ROOT}/scripts/dae_infra.py ensure <names>` (reading the manifest's `infra:` section). On a `start-failed` failure → stop and surface the structured diagnosis. On undeclared required infra → stop with "declare in manifest" message. This applies to Steps 3, 4, 7.

**Quirks contract.** Before booting infra or running test commands, consult `manifest.infra_quirks`: apply `runtime_pins` (e.g. ensure `JAVA_HOME` matches `runtime_pins.java`), read `port_map_file` if set, surface `framework_constraints` to the agent if relevant ("note: Flutter web has no hot-reload — full rebuild required"), use `recovery_commands` keyed by failure signature when probing reports a known stuck state, and — when reproducing against a worktree whose app is mount-served — follow `worktree_preview` instead of rediscovering the mount switch. Quirks exist so the agent doesn't rediscover what's already documented (nexthq Java/Flutter, mmc Apache opcache).

**Fixture-parity contract.** Steps 3, 4, and 7 run the regression spec / acceptance / mutation against a seeded DB. If `manifest.acceptance.fixture_parity.check` is set, run that command FIRST as a hard gate — non-zero means the seed fixture has drifted from the schema/migrations: **stop, report the drift, do not run the tests, and do not attribute the resulting RED to code.** Even with no check configured, never diagnose a RED as fixture drift without proving it (diff the fixture against the schema) — a phantom-column fixture masks real defects. See `${CLAUDE_PLUGIN_ROOT}/references/fixture-parity.md`.

### Step 0 — Re-entry routing

Before Step 1, probe for in-flight fixes via `${CLAUDE_PLUGIN_ROOT}/scripts/dae_fix.py list_open_fixes` (any status != `closed`). Three cases:

| State | Action |
|---|---|
| **No open fixes** | Proceed to Step 1 (Capture) as a new defect. |
| **Exactly one open fix, agent has fresh context** (e.g. just typed "still failing", "validation failed again") | Continue that fix from its current `status:` — jump to the matching step. Don't write a new artifact. |
| **Multiple open fixes**, or **one open fix + trigger sounds like a new defect** (e.g. "another bug", "a new report came in") | Surface the open fixes one-line each and ask "continue X, or capture a new defect?" — single AskUserQuestion, then proceed. |

mmc ran 5 sequential fixes from one `/engineer.fix` invocation because the skill assumed one-shot. Re-entry routing makes "many fixes in a row" cheap: no re-anchor, no template re-read, just pick up where the last close left off. A fresh defect from re-entry still flows through Steps 1–9 — it just doesn't lose the agent's context to a cold start.

### Step 1 — Capture

Accept free-form input; no feature slug required. Collect: title, severity (`low | medium | high | critical`), source (`kind: sentry|github|slack|user|internal`, `ref: <url-or-id>`), whether it blocks users (`blocks_user`), workaround (`"none"` if none), and a concise repro/expected/actual. **This capture is the bug intent** (`${CLAUDE_PLUGIN_ROOT}/references/intent.md`) — synthesized from whatever signal arrived (a Sentry alert, stack trace, Slack message, or raw log), exactly as `discuss` synthesizes a feature intent.

Write `.engineer/fixes/<YYYY-MM-DD-slug>.md` via the schema in `references/artifact-template.md`. Set `status: investigating`.

CLI shortcut: `/engineer.fix "title" --source <url>` pre-fills title and source; skip the prompt for those fields.

**From a tracker capture:** if this fix is being promoted from an untriaged tracker row (a bug a human added directly — no `Slug`; see *Tracker-as-intake* in `engineer/references/tracker.md`), pre-fill title / severity / source from the row, set the fix's `tracker_ref` to that row, and write the fix slug back to it — don't leave the row orphaned or create a duplicate.

Validate the new artifact: `${CLAUDE_PLUGIN_ROOT}/scripts/dae_fix.py --validate <fix-file>`. Surface any errors before proceeding.

### Step 2 — Investigate

**Goal:** identify which feature(s) own the broken code.

Heuristics — run cheapest first to bound token cost:
1. Stack trace files → cross-reference `feature.files` in known features.
2. Error text grep across `.engineer/features/*/feature.md`.
3. Recent commits on the affected path (`git log --oneline -- <file>`).
4. User-provided hints.
5. From the failing symbol, trace root cause and blast radius via LSP — `findReferences` + call-hierarchy (`incomingCalls`) to see who reaches the broken code — when an LSP MCP capability is available; fall back to grep otherwise. See `${CLAUDE_PLUGIN_ROOT}/references/code-lookup.md`.

**Match resolution:**
- Single clean candidate and `prime-context` confirms strong relevance → AUTO-POPULATE `feature_refs`; record `match_mode: auto`.
- Multiple candidates or ambiguous → rank top 3, invoke `prime-context` per candidate, present ranked list, ask user to confirm. Record `match_mode: manual`.
- No match → record `match_mode: none`; proceed as a loose fix (no `feature_refs`).

Record `investigation.candidates_considered`. Set `status: pinned-pending`.

### Step 3 — Pin (CONFIRM-FIRST GATE 1)

Write one regression Given/When/Then spec **per `feature_refs` entry** (not a shared spec). Use `references/regression-spec-template.md`.

Run the spec on current code. It **MUST be RED**. If it passes (GREEN) the spec does not pin the bug — redraft until RED. Record `red_run.result: red` + command + output in `pin_confirmation.feature_refs[*]`.

Present the spec(s) and red-run evidence to the user for confirmation before proceeding. Set `status: pinned`.

### Step 4 — Fix (CP5-style)

Implement the fix using the same discipline as Checkpoint 5. The regression spec must turn GREEN. Update `fix_commits`. Set `status: fixed`.

### Step 5 — Refine (CP6)

Invoke `engineer:refine` on touched code. Set `status: refined`.

### Step 6 — Verify (CP7)

Run `engineer:arch-check` on each touched feature. Run `crap-analyzer` on the fix diff. Record results. Set `status: verified`.

### Step 7 — Harden (CP8 + CONFIRM-FIRST GATE 2)

**Introversion pre-scan (cheap, runs first).** Before mutation, run `${CLAUDE_PLUGIN_ROOT}/scripts/dae_introvert.py <methodology-root>` — it flags *introverted* tests that can pass without asserting on SUT output (`no-assertion`, and `conditional-assertion` where every assertion is nested in a conditional/loop/try, the classic vacuous-test case). It defers to a real backend when `manifest.introversion.backend` is set (e.g. a `deintroverter` that backward-slices each assertion to the SUT) and otherwise runs a built-in Python-AST fallback; any non-`ok` status is advisory — proceed. For each finding, dispatch an agent to inspect the test and confirm whether it is vacuous; fold confirmed cases into the harden report and treat them like surviving mutants (write a real assertion, then re-run). A test flagged here **and** later carrying a surviving mutant is a high-confidence vacuous test. Record `harden_results.introversion`.

Run `atdd:atdd-mutate` on touched files. Record `harden_results.mutation_score`.

**Bug-line mutation gate:** recover the buggy line(s) via `git show HEAD~1 -- <file>`, apply locally, run only the regression spec, assert RED. If the spec stays GREEN the spec is coupled to the fix, not the bug — back to Step 3 (Pin). Restore the fix. Record `harden_results.bug_line_mutation_confirmed: true`.

Record `harden_results.arch_check`. Set `status: hardened`.

### Step 8 — Gap analysis ("why didn't we catch it?")

For each affected feature, identify which DAE phase leaked. Use the closed vocabulary in `references/gap-analysis-categories.md` — one entry per distinct finding.

**CONFIRM-FIRST:** present findings to the user for approval before writing to the artifact. Findings are claims about methodology gaps; the user is the source of truth.

Write approved findings to `gap_analysis[*]`. Determine blockers via `blocker_categories()` (see `references/gap-analysis-categories.md` for the rule). Advisory followups go to `.engineer/consolidation.md` tagged with the fix slug; blocker followups must be applied inline or the charter explicitly amended. Set `status: gap-analyzed`.

### Step 9 — Close

Run `${CLAUDE_PLUGIN_ROOT}/scripts/dae_fix.py` `close_ready(rec)`. Hard preconditions: pin confirmed, hardened (including bug-line gate), `gap_analysis` non-empty, no unresolved blockers.

Emit a handoff that reference-links each `feature_refs[*]/progress.md`. Set `status: closed`.

Then dispatch per `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md`: advisory followups already landed in `.engineer/consolidation.md` (no dispatch — `next` surfaces them); blocker followups are already applied. Auto-invoke `/engineer.progress-log` to propagate the closure entry to each affected feature's `progress.md` at autonomy `medium`/`high`; confirm-then-dispatch at `low`.

**Post-merge cleanup (deferred).** Print the cleanup commands the user (or next agent) must run *after* the fix PR merges, and record the branch name in the closure entry so `next`/`session-summary` can detect a stale branch later:

```
After the PR merges:
  git checkout main && git pull --ff-only && git branch -d <branch>
```

This is informational — the close step happens before merge, so cleanup can't run here. `next` and `session-summary` both probe for merged branches and will offer the cleanup automatically.

## When NOT to use this skill

- Building a new feature → `/engineer.discuss` or `/engineer.feature-init`
- Refining an in-flight feature's scope → `/engineer.feature-edit`
- Reviewing recent changes without a defect → `/engineer.verify` or `/crap-analyzer`

## References

- `references/artifact-template.md` — canonical `.engineer/fixes/<slug>.md` schema
- `references/regression-spec-template.md` — Given/When/Then template used in Step 3
- `references/gap-analysis-categories.md` — closed vocabulary + blocker rule
- Sister skills: `prime-context` (Step 2 per candidate), `arch-check` + `crap-analyzer` (Step 6), `atdd-mutate` (Step 7), `progress-log` (Step 9), `next` (surfaces open fixes)
- `engineer/references/handoff-dispatch.md` — infra-ensure-before-stop rule
