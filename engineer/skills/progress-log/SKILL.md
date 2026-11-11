---
name: progress-log
description: Use to propagate DAE state — turning handoff summaries into visible progress. Triggers — "/engineer.progress-log", "sync progress", "update the tracker", "reconcile the tracker", "refresh feature status".
---

# progress-log

The propagation engine of DAE visibility. Skills emit handoff summaries; `progress-log` turns them into the two visible state layers — `progress.md` (the per-feature glanceable file) and the external tracker.

When the foundations say "the agentic summary contract handles propagation," this skill *is* that propagation. `checkpoint: null`.

## When to use

- **Auto** — invoked after a handoff-emitting skill changes a DAE-managed field (status change, checkpoint completion). Scope = the triggering feature.
- **Manual** — `/engineer.progress-log <slug>` re-syncs one feature; `--project` reconciles all.

**Not for:** changing artifacts (`feature-edit`); validating consistency (`consistency-check`); a session wrap-up (`session-summary`).

## Workflow

1. **Resolve + scope** — resolve the methodology root + manifest via `${CLAUDE_PLUGIN_ROOT}/scripts/dae_resolve.py` (see `references/resolving.md`); the manifest carries the tracker config. Scope = one feature (auto / `<slug>`) or all (`--project`).
2. **Read new handoffs** — `handoffs/*.md` not yet reflected in `progress.md` (compare timestamps against the last-synced marker).
3. **Update `progress.md`** — per handoff: update the Checkpoints table row (if `checkpoint:` set), append to Verification reports (if a verification skill), append to the Handoff log, recompute the **CURRENT header** — the fixed, parseable first line of `progress.md`: `> ▶ CP<N> <Stage> — <m>/<n> criteria met | NEXT: <action> | BLOCKED: <none|reason>`. Derive `<m>/<n>` from the latest handoff's `exit_criteria` block for the current checkpoint, `NEXT` from its `recommended_next`, and `BLOCKED` from any unmet criterion that needs a human (else `none`). If the handoff carries a `cloud_session_url` and its PR isn't merged yet, set `NEXT: review cloud PR <url>` and record the session/PR link in the Handoff log — this is the signal `next` reads to surface the feature as DISPATCHED.
4. **Recompute tracked state** — derive the `TrackedFeature` record from local truth (`feature.md` + `progress.md`).
5. **Sync the tracker** — driver `upsert(TrackedFeature)` per `references/tracker.md`: local-wins on DAE-managed fields, tracker-managed fields (comments, labels) preserved. `local` = no-op (the feature files are the tracker). Write the result to `progress.md`'s "Tracker sync" line.
5b. **Sync the roadmap (if the feature came from one)** — if `feature.md` carries a `roadmap_ref`, keep the strategic item's lifecycle in step with the feature: on `status: in-progress` ensure the item is `in-progress` with the feature's slug back-linked; on `status: done` (written in the ship commit, before merge) mark it `shipped`. Driver per `references/roadmap.md` (`local` = `${CLAUDE_PLUGIN_ROOT}/scripts/dae_roadmap.py mark <roadmap_ref> <status> <slug>`; MCP/CLI/API-backed = the connected channel). If `manifest.roadmap.type` is `none` or the host is unreachable, skip with a one-line note — never block the tracker sync. Note the result on `progress.md`'s "Tracker sync" line.
6. **(`--project` only) Merged-PR reconcile + drift report** — first, for each in-flight feature run `${CLAUDE_PLUGIN_ROOT}/scripts/dae_reconcile.py <feature-dir> --apply`: it flips `feature.md status: done` for any feature whose PR is merged (detected via `gh`, so **squash-merge and `git.manual` are covered**) so the tracker sync below reflects git reality instead of stale `in-progress`. A returned `flag: merged-unverified` (shipped with no CP7 verify handoff) is a discipline gap — surface it, don't bury it. Then run driver `reconcile()` per `references/tracker.md`; surface anything unexpected (orphan tracker entry, untracked local feature).

## Ship commit vs. post-merge

progress-log writes `progress.md` (and the roadmap `shipped` mark) on the feature
branch inside the ship commit (`dae_ship.py`, from harden / express), not after
merge. Post-merge invokes it for the external tracker only (`merged_at` lives
there, never in tracked files). In `--project` mode, `dae_reconcile.py --apply`
(step 6) is the backstop for ship-less features only; a feature already `done` is
a no-op.

## Handoff exemption

**progress-log does NOT emit a handoff summary** — it is the single exception to the agentic summary contract. It is the mechanism that *processes* handoffs; emitting one would trigger another progress-log run, looping. Its record of work is the `progress.md` "Tracker sync" line. (Documented in the Foundation Design.)

## Logging a fix closure

When the `fix` skill reaches its Close step, append the rendered closure entry
to each `feature_refs[*]/progress.md` of the fix artifact.

Use `${CLAUDE_PLUGIN_ROOT}/scripts/dae_fix.py` helper `render_fix_closure_entry(rec, followups_summary)`
to build the entry. Append it to each affected feature's progress.md under a new
H2 section (the helper produces a complete H2 + bullets block).

Fix closures use the same propagation contract as feature handoffs: visible at
the feature level so contributors browsing that feature see the bug history
without having to discover `.engineer/fixes/`.

## ATDD team teardown

When `progress-log` observes a feature advancing to `status: done` (CP8 complete
or PR merged), check whether an `atdd-<slug>` team exists. If it does, propose
teardown per the `atdd:atdd-team` lifecycle — auto-dispatch at autonomy
`high`/`medium`, surface and wait at `low`. nexthq saw a team idle for 5 days
after its feature shipped because nothing claimed responsibility for cleanup.

## References

- [Foundation Design](https://www.notion.so/3585ecdee0e2811bbc67ff4913c03207) — `progress.md` schema, agentic summary contract + this exemption (Section 5)
- `references/tracker.md` — the tracker drivers, `TrackedFeature`, local-wins reconciliation
- `references/roadmap.md` — the roadmap drivers; shipping a roadmap item on feature `done`
- [Tracker Integration](https://www.notion.so/35a5ecdee0e28168b1aee324c267fd13) — sync triggers, the column schema
