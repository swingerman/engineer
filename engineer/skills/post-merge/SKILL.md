---
name: post-merge
description: Use immediately after a PR is merged to clean up the local feature branch and resync main. Triggers — "/engineer.post-merge", "did we merge", "did we push", "PR merged", "post-merge cleanup", or right after a `gh pr merge` succeeds in the same session.
---

# post-merge

The branch-hygiene skill that runs **immediately** after a PR merges — not deferred to the next session. `next` and `session-summary` already catch a stale branch at session boundaries (v1.7.1); `post-merge` closes the gap in between, where users were still asking *"are we still on the feature branch?"* mid-session.

## When to use

- **Auto** — invoke right after observing a successful `gh pr merge`, `gh pr merge --auto`, or a "Merged" PR state in `gh pr view --json state`. The agent that ran the merge calls this skill before doing anything else.
- **Manual** — `/engineer.post-merge` or the trigger phrases above.

**Not for:** cleanup when the PR isn't merged yet (the work isn't done); session-end teardown (`session-summary` handles that); session-start survey (`next` already probes for stale branches as a backstop).

## Workflow

1. **Resolve + identify merged branch.** Resolve the methodology root via `${CLAUDE_PLUGIN_ROOT}/scripts/dae_resolve.py`. Get the current branch (`git branch --show-current`). If it's `main`/`master`/the repo's default branch, there's nothing to clean — stop and report.

2. **Probe merge state.** Run `git fetch origin --quiet`, then check whether the current branch has been merged:
   - **GitHub-side check** (preferred when `gh` is available): `gh pr view --json state,mergedAt,headRefName --jq '.state'` for the PR linked to this branch. State of `MERGED` is the strongest signal.
   - **Git-side check** (fallback): `git merge-base --is-ancestor HEAD origin/HEAD` (or `origin/main`). True means every commit on this branch is reachable from main.

   If neither check confirms a merge, stop — the work isn't shipped yet. Report what was checked.

3. **Run the cleanup.** Run the three commands in order, stopping on any non-zero exit:
   ```
   git checkout <default-branch>
   git pull --ff-only
   git branch -d <merged-branch>
   ```
   `git branch -d` (not `-D`) refuses unmerged work — non-destructive by construction. If it refuses, surface what's unmerged and stop; don't escalate to `-D` without explicit user confirmation.

4. **Prune stale remote refs.** `git fetch origin --prune`. Removes pointers to remote branches that no longer exist (e.g. when the GitHub "delete branch on merge" setting removed the remote).

5. **Reconcile local state, then the tracker.** Flip the *local* `feature.md` status FIRST — otherwise `progress-log` (which derives the tracker record from local truth) and `next`/`reorient` (which read `feature.md status`) keep seeing `in-progress`. Run:
   ```
   ${CLAUDE_PLUGIN_ROOT}/scripts/dae_reconcile.py <merged-feature-dir> --apply
   ```
   It sets `feature.md status: done` when the PR is merged (detected via `gh`, so **squash-merge and `git.manual` are covered** — the git-ancestry check in Step 2 is not) and returns `flag: merged-unverified` when no CP7 verify handoff exists. **If flagged, surface it prominently** — the feature shipped with its ACs unverified; that is a discipline gap, not a clean close. Then dispatch `/engineer.progress-log` to propagate the done state to `progress.md` + the tracker (records `merged_at`). Per `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md` — auto at `medium`/`high`, surface-and-ask at `low`.

5b. **Feature map.** If the merged feature added a user-facing surface and the `verify-<app>` skill (`manifest.verify_app`) has no row for it, add the row (feature → how to reach it → what working looks like) per `${CLAUDE_PLUGIN_ROOT}/references/verify-app-skill.md`. Committing it follows the Autonomy dispatch below. Feature maps fall behind when a missing row goes unnoticed, so don't skip this.

6. **Close the session log.** A merged feature is the clearest session boundary there is — the work shipped and the next session starts somewhere else. Auto-invoke `/engineer.session-summary` at autonomy `medium`/`high`; confirm-then-invoke at `low`. This is the human-readable "how do I pick this up" record; without it the only trace of the session is machine handoffs. Skip if a session-summary entry for today already exists on this feature.

7. **Handoff.** Emit a summary per `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md`. `checkpoint: null`; `artifacts: []`; `human_action_needed: no`. The handoff records: the merged branch name, the PR URL (if known), and the new HEAD commit. `recommended_next` points at `/engineer.next` if the feature is shipped, or the relevant fix/session continuation otherwise.

## Autonomy dispatch

| Level | Behavior |
|---|---|
| `high` | Run all seven steps. Report a one-line summary. |
| `medium` | Run all seven steps. Report what changed (one short paragraph). |
| `low` | Surface the planned commands and the merge-state evidence; wait for confirmation before running. |

## When NOT to use this skill

- The PR is open or in review → wait until it's actually merged.
- The merge happened on a *different* branch than the one currently checked out → switch to that branch first (or just `git fetch --prune` and skip the rest).
- You squashed and force-pushed → `git branch -d` will refuse; that's expected. Either confirm `-D` manually or rebase onto main and try again.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md` — handoff schema
- `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md` — autonomy-driven dispatch rule
- Sister skills: `next` (session-start stale-branch backstop), `session-summary` (session-end stale-branch backstop), `progress-log` (tracker propagation)
