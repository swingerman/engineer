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

5. **Backstop reconcile (read-only).** Features shipped via the ship commit
   (`dae_ship.py`, written by harden / express before the PR) already carry
   `status: done` on main, so **post-merge writes nothing tracked on main** and
   leaves `git status` clean. Run
   ```
   ${CLAUDE_PLUGIN_ROOT}/scripts/dae_reconcile.py <merged-feature-dir>
   ```
   read-only. `needs_reconcile: false` = done, nothing to do. Only for legacy,
   onboarded and `git.manual` features that never got a ship commit
   (`needs_reconcile: true`) re-run with `--apply`, and commit that flip via a
   PR (these are the only cases that still need a commit on main). A
   `flag: merged-unverified` is surfaced prominently: the refusal at ship time
   should have prevented it, so it means a ship-less merge.

5b. **External tracker sync only.** If a tracker is configured, push the merge
   (it may record `merged_at` there; never in tracked files). No file writes.

6. **Session log.** The session-summary entry lives in the ship commit when
   `session-log.md` is in the repo. Auto-invoke `/engineer.session-summary`
   post-merge only if the log is outside the repo, or the feature had no ship
   commit; the entry then goes external-only, never a new commit on main.

7. **Handoff.** Emit a summary per `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md`. `checkpoint: null`; `artifacts: []`; `human_action_needed: no`. The handoff records: the merged branch name, the PR URL (if known), and the new HEAD commit. `recommended_next` points at `/engineer.next` if the feature is shipped, or the relevant fix/session continuation otherwise.

## Autonomy dispatch

| Level | Behavior |
|---|---|
| `high` | Run all steps. Report a one-line summary. |
| `medium` | Run all steps. Report what changed (one short paragraph). |
| `low` | Surface the planned commands and the merge-state evidence; wait for confirmation before running. |

## When NOT to use this skill

- The PR is open or in review → wait until it's actually merged.
- The merge happened on a *different* branch than the one currently checked out → switch to that branch first (or just `git fetch --prune` and skip the rest).
- You squashed and force-pushed → `git branch -d` will refuse; that's expected. Either confirm `-D` manually or rebase onto main and try again.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md` — handoff schema
- `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md` — autonomy-driven dispatch rule
- Sister skills: `next` (session-start stale-branch backstop), `session-summary` (session-end stale-branch backstop), `progress-log` (tracker propagation)
