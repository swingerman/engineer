# verify-<app> — the project's real-app skill

Tests check the spec. Arch-check and CRAP check the code's shape. Neither one
runs the real artifact. The verify skill does that: a project-local skill that
launches the app, drives it the way a user would, and captures evidence that
it works.

`/engineer.onboard` generates it at `.claude/skills/verify-<app>/SKILL.md`
(`<app>` = the project's short name, kebab-case) and records the name in
`manifest.verify_app`. CP7 (`arch-check`, run by the `verifier` agent) and the
verify step of `/engineer.fix` call it. `dae_handoff.py` will not count a CP7
handoff as complete unless it has a `real_run` block that names this skill and
points at evidence files that exist and are non-empty. `harden`'s entry gate and
`dae_mergeready` both check this.

**Rollout.** The block applies to features whose `feature.md` `created:` date
is on or after `REAL_RUN_CUTOFF` in `dae_handoff.py`. Older features, and
features with no `created:`, were already in flight when the gate shipped:
their CP7 still passes, but the gate prints a warning.

A project with nothing to run (a pure library with no CLI, demo, or example)
sets `verify_app: none` in the manifest. This is an explicit opt-out that a
reviewer can see. If `verify_app` is missing, CP7 is blocked for new features.

## Template

Fill each section from the manifest (`infra:`, `infra_quirks`,
`validation.staging`) and the repo (package scripts, Makefile, README run
instructions, routes, CLI entry points). Every command must be real and
copy-pasteable. Don't write prose like "start the app".

```markdown
---
name: verify-<app>
description: Launch <app>, drive it like a user, and capture evidence that a feature works. Used by CP7 verify and /engineer.fix. Triggers — "verify <app>", "run the real app", "prove it works".
---

# verify-<app>

## Launch
<exact commands, in order. Use `dae_infra.py ensure <names>` for declared
infra, then the app's own start command. Apply runtime_pins, port_map_file,
and worktree_preview from infra_quirks.>

## Doctor
<one command that exits 0 only when the app is healthy, e.g.
`curl -fsS localhost:3000/health`, or `<cli> --version`. If it fails, check
recovery_commands from infra_quirks, then stop and report. Never drive an
unhealthy app.>

## Drive
<how to exercise the app: CLI invocations, HTTP calls (curl), or browser steps
(Claude in Chrome / Playwright). Give one worked example per surface kind.>

## Evidence
Write everything to `features/<slug>/evidence/` (for fix: `<fix-dir>/evidence/`),
which is committed with the feature:
- `run-<timestamp>.log`: the commands that ran and their real output
- <per surface: HTTP response bodies, CLI stdout, screenshots (.png)>
A file that would be empty means the run failed. Don't write it.

## Cleanup
<stop what Launch started, e.g. `dae_infra.py` teardown, kill the dev server,
remove temp data.>

## Feature map
| Feature | How to reach it | What working looks like |
|---|---|---|
| <slug> | <URL / command / UI path> | <observable result: status + body field, stdout line, visible element> |
```

## Proof run (onboard)

Onboard is not complete until the skill has run once from start to finish:
Launch → Doctor → Drive the top feature-map row → Evidence → Cleanup.
Evidence goes to `.engineer/evidence/onboard/`. A failed proof run means
onboard is not done: fix the skill and run it again. Emit
`status: interrupted` if you cannot fix it.

## Handoff block (CP7 / fix verify)

```yaml
real_run:
  skill: verify-<app>                   # must equal manifest.verify_app
  features: [<feature-map rows driven>]
  evidence:                             # paths relative to methodology root
    - features/NNN-<slug>/evidence/run-<ts>.log
```

The CP7 criterion "feature works in the real app" is `verified_by: tool`, and
its `evidence` line quotes the observed result from the run log. A passing test
suite is not evidence for this criterion.

## Maintenance

The feature map has to match the app's surfaces. `/engineer.feature-edit` and
`/engineer.post-merge` add or update the row when a feature adds or changes a
surface (a route, a command, a screen). CP7 cannot drive a feature that has no
row, so add the row before verifying.
