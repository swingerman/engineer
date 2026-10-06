---
name: next
description: Use at the start of a work session, or any time the question is "what should I pick up now" across the whole project. Triggers — "/engineer.next", "what's next", "what should I work on", "what should I do next", "where do I pick up".
---

# next

The session-start skill — the human's re-entry point. Surveys every source of DAE state and answers one question: **what should I pick up now?**

Read-only and advisory. It changes nothing, produces no artifact, and emits **no handoff** (the recommendation is the whole output; a handoff would just restate it). This is a deliberate exception to the agentic-summary contract — `next` is a query, not a task that changes state.

`next` is the read-side bookend to `session-summary`: `session-summary` writes "here's where I left off, next tasks" at session end; `next` consumes that — and everything else — at session start.

## When to use

Start of a session, or any "what now?" moment. Project-scope; surveys the whole project — there is no narrower scope.

**Not for:** loading context on a feature you've already chosen (`prime-context`); checking artifact consistency (`consistency-check`); a per-feature next-step (each skill's handoff already carries `recommended_next`).

## Workflow

### Step 1 — Resolve and survey

Resolve the methodology root + manifest via `${CLAUDE_PLUGIN_ROOT}/scripts/dae_resolve.py` (see `references/resolving.md`). Then read, read-only:

- **In-flight features** — every `features/*/feature.md` (status) + `progress.md` (current checkpoint; whether it's blocked or ready to advance). For each in-flight feature, run `${CLAUDE_PLUGIN_ROOT}/scripts/dae_reconcile.py <feature-dir>` (read-only): if it reports `needs_reconcile: true`, the feature's PR is merged but its local state hasn't caught up — this is the authoritative merged-detection (via `gh`, so it catches **squash-merge and `git.manual`**, which the current-branch git-ancestry check below misses). Surface these under NEEDS YOUR DECISION and, at autonomy `medium`/`high`, offer `/engineer.post-merge` to reconcile (which flips the status and propagates). A `flag: merged-unverified` means it shipped without CP7 — call that out.
- **Consolidation backlog** — `.engineer/consolidation.md` if present (coverage backlog + triage order)
- **Roadmap (strategic feature list)** — the next *unstarted* roadmap item(s) via the driver (`local` = `${CLAUDE_PLUGIN_ROOT}/scripts/dae_roadmap.py next-unstarted`; MCP/CLI/API-backed = the connected channel — see `references/roadmap.md`). This is the **"what's next in the roadmap"** altitude — candidate features not yet promoted to a feature folder, the forward-looking complement to the consolidation backlog. If `manifest.roadmap.type` is `none`, or its host is unreachable (MCP disconnected / CLI gone), **skip it with a one-line note** — degrade gracefully, never error.
- **Parked ideas** — `features/*/` with `status: parked`; `.engineer/discussions.log`
- **Tracker captures (triage queue)** — tasks a human added *directly to the onboarded tracker*: rows with no `Slug` yet (the `reconcile()` orphan-as-intake case, see `references/tracker.md`), or `.engineer/inbox.md` lines in local mode. These are quick-captured bugs/ideas/tasks awaiting triage — not yet a feature or fix.
- **Pending human actions** — recent `handoffs/*.md` (per-feature and `.engineer/handoffs/`) flagged `human_action_needed: yes`
- **Session-log next-tasks** — the latest `session-log.md` entry per active feature ("Next tasks")
- **Dispatched to cloud** — features whose latest handoff carries `cloud_session_url` (running on a cloud agent; PR pending). Surface as DISPATCHED — not actionable until the PR lands.
- **CHARTER.md + manifest** — autonomy levels and path overrides, for execution-mode advice
- **Open fixes** — `.engineer/fixes/*.md` via `${CLAUDE_PLUGIN_ROOT}/scripts/dae_fix.py list_open_fixes` (status != closed)
- **Stale merged branch** — if the current branch is not `main`/`master`, run `git fetch origin --quiet` then check `git merge-base --is-ancestor HEAD origin/HEAD` (fallback `origin/main`). If true, the branch is merged and lingering — surface it as a STALE BRANCH item. (This git check only catches the *current* branch and only non-squash merges; the per-feature `dae_reconcile.py` probe above is the broader, `gh`-based merged-detection.)

### Step 1.5 — Offer branch cleanup (if stale)

If a stale merged branch was detected, defer to the `post-merge` skill — it owns the full cleanup flow (checkout, pull, branch -d, prune, tracker update). At autonomy `high`/`medium`, auto-invoke `/engineer.post-merge` before continuing to Step 2. At `low`, surface the finding and stop until the user invokes it themselves. Do not inline the cleanup commands here — keep `next` advisory and let the dedicated skill do the work, so the post-merge handoff lands in the audit trail.

### Step 2 — Triage into eight buckets

```
NEEDS YOUR DECISION   — blocked features; handoffs flagged human_action_needed.
                        These stall progress — surface them first.
OPEN FIXES            — bug-fix artifacts not yet closed. Sub-priority within the bucket:
                         1. blocks_user: true AND workaround: none      ← top (user is hit right now)
                         2. blocks_user: true AND workaround: <text>    ← middle (user has a workaround)
                         3. blocks_user: false                          ← bottom
                         Within each tier, order by severity (critical, high, medium, low).
READY TO ADVANCE      — in-flight features sitting at a checkpoint that can proceed.
READY TO DISPATCH     — features / consolidation tasks that can go to a cloud agent
                        right now (bounded, automatable verification, no mid-stream
                        human input needed). At medium/high autonomy the dispatch
                        router auto-sends these (gated by dae_delegable.py).
DISPATCHED            — already running on a cloud agent (handoff carries
                        cloud_session_url). Show the session / PR link; review when
                        it lands. Not actionable until then.
TRIAGE                — tasks added directly to the tracker (a row with no Slug
                        yet) or to .engineer/inbox.md — bugs/ideas/tasks dropped
                        in for DAE to pick up, not yet a feature or fix. For each:
                        promote (→ /fix, /discuss, /feature-init) or defer. A
                        triage bug that blocks users ranks with OPEN FIXES top tier.
ON THE ROADMAP        — the next unstarted strategic feature(s) — roadmap items
                        (status: planned, no feature_slug yet), ordered by
                        horizon (now → next → later) then priority. This is the
                        "what's next in the roadmap" answer: the highest-altitude
                        candidate to START, distinct from finishing in-flight
                        work. Promote via /discuss or /feature-init (writes
                        roadmap_ref + marks the item in-progress — see
                        references/roadmap.md). Items already in-flight (they
                        carry a feature_slug) are hidden here — they appear under
                        READY TO ADVANCE instead.
COULD START           — the next consolidation-backlog item; parked ideas worth
                        promoting; fresh work.
```

### Step 3 — Rank and recommend

Priority order:
1. **Unblocking first** — a blocked feature or a pending human-action stalls everything downstream; clearing it usually beats starting something new.
1b. **User-blocking defects** — an OPEN FIX with `blocks_user: true` and no workaround ranks above starting fresh feature work; a real defect hitting users now is more urgent than forward progress on new scope. A TRIAGE capture that reads as a user-blocking bug ranks here too — promote it to a `/fix` first.
2. **Triage priority / dates** — consolidation-backlog order, feature `target` dates.
3. **Dispatchability** — if the human has limited time, favour surfacing what can be *dispatched* (freeing the human) over what *needs* them.

Present the eight buckets, then a **two-altitude answer** — because "what's next" has two valid readings and the human asked for both:
- **Next to ADVANCE/finish** — the single best *actionable* next step across in-flight work, fixes, and dispatch (the existing top pick). Unblocking and user-blocking defects win here.
- **Next to START** — the top `ON THE ROADMAP` item: the next strategic feature to begin once there's capacity. Always shown so "what's next *in the roadmap*" is answered directly, even when the top actionable pick is finishing something else.

Give one top recommendation with a one-line rationale and a suggested execution mode (you, local subagent, agent team, **coordinated**, or cloud agent — for the last, the dispatch router gates via `dae_delegable.py`). Suggest **coordinated** (`/engineer.run <slug>`, see `${CLAUDE_PLUGIN_ROOT}/references/coordinator.md`) for a non-express feature at autonomy `medium`/`high` that has two or more checkpoints left before CP8. It resumes from the latest complete checkpoint, so a half-done feature qualifies. name the roadmap's next-to-start alongside it. If in-flight work is clear (nothing to advance, no open fixes), the roadmap's next-to-start *becomes* the top pick.

**Promoting a TRIAGE item** is the human's call — `next` only recommends. *Work it now* → promote to the right unit and start: bug→`/fix`, idea→`/discuss`, task→`/feature-init` (each reads the tracker row as intake, reuses its `tracker_ref`, and writes the assigned `Slug` back — no duplicate row). *Later* → leave it, optionally raise a `priority`/`Status`. *Drop* → set `Status: wontfix`.

### Step 4 — Stop

`next` recommends; it does **not** act. The human picks, then invokes the relevant skill themselves (`prime-context`, `discuss`, `feature-init`, a consolidation task, …). No handoff is emitted.

## Example shape

```
NEEDS YOUR DECISION (1)
  • 042-customer-export — plan.md has a charter deviation; approve amendment ADR-012 or revise

OPEN FIXES (2)
  • 2026-05-20-login-crash [critical] blocks_user=true workaround=none — login fails on iOS 17
  • 2026-05-18-export-timeout [high] blocks_user=true workaround="retry after 30 s"

READY TO ADVANCE (1)
  • 015-image-formats — at Checkpoint 2; ACs done, ready for /atdd:atdd (or /engineer.run 015-image-formats to drive CP3→CP8)

READY TO DISPATCH (2)
  • consolidation #1 core-image-generation — full ATDD coverage; remote one-shot
  • consolidation #3 mcp-connector — remote one-shot

TRIAGE (2)
  • bug: CSV export drops the UTF-8 BOM | blocks_user=yes — added to tracker, no slug yet
  • idea: dark mode for the settings page

ON THE ROADMAP (2)
  • bulk-export [now/p1] — admins export all records as CSV; not yet started
  • dark-mode [next/p1] — settings dark theme

COULD START (1)
  • parked: bulk-admin-export — discussed 3 weeks ago; promote if priorities allow

→ TOP PICK (advance): fix 2026-05-20-login-crash. Users are hitting a critical crash
  on iOS 17 with no workaround — this outranks new feature work. Run /fix to continue.
  Then approve 042-customer-export's plan to unblock its pipeline.
→ NEXT TO START (roadmap): bulk-export — the top "now" item, unstarted. When the
  crash is cleared, promote it with /discuss or /feature-init.
```

## When NOT to use this skill

- You already know the feature and just need to start → `prime-context`
- You want full project state validated, not a recommendation → `consistency-check --project`
- You want to wrap up a session → `session-summary`

## References

- [Foundation Design](https://www.notion.so/3585ecdee0e2811bbc67ff4913c03207) — feature.md / progress.md / agentic summary schemas
- The DAE methodology page — the three-layer visibility model; the parallelism model (one human driving several pipelines)
- Sister skill: `session-summary` — the session-end bookend.
- Sister skill: `fix` — produces the OPEN FIXES artifacts surfaced here.
- `references/roadmap.md` — the roadmap drivers behind the ON THE ROADMAP bucket; `dae_roadmap.py next-unstarted`.
- `${CLAUDE_PLUGIN_ROOT}/references/host-capabilities.md` — the optional **render** capability. Eight buckets of in-flight work is a dashboard wearing a list's clothing; offer a rendered board alongside — never instead of — the text survey.
