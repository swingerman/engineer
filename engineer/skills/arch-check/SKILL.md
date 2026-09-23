---
name: arch-check
description: Use to check a feature's code against the charter's architecture rules — dependency layering, cycles, forbidden patterns, file naming, file size. Triggers — "/engineer.arch-check", "architecture check", "check architecture fitness", "does this follow the charter", "check layering".
---

# arch-check

Run the charter architecture fitness check — Checkpoint 7 (Light Verify),
alongside `crap-analyzer`. Turns the charter's architectural vision from prose
into an objective gate: `dae_arch.py` reads the manifest's `architecture:` rules
and reports violations.

Read-only on the codebase — it reports, it does not fix.

## When to use

Checkpoint 7, after the feature's code is implemented and refined. Also useful
as a standalone audit (`--full`) of an existing project.

**Not for:** change-risk analysis (`crap-analyzer`); artifact consistency
(`consistency-check`); fixing violations (that is a human/agent decision per
violation).

## Workflow

### Step 0 — Entry gate

Verify the prior checkpoint is complete: run
`${CLAUDE_PLUGIN_ROOT}/scripts/dae_handoff.py <feature-dir> --through 6`. On a
non-zero exit, **stop** and surface the gap to the human.

Verify branch hygiene: run `${CLAUDE_PLUGIN_ROOT}/scripts/dae_branch.py <feature-dir>`.
On a non-zero exit, **stop** and surface the message to the human — switch
branches and re-invoke. The check honors the `git.manual: true` manifest
opt-out.

After the gate passes, show the **pipeline breadcrumb**: run
`${CLAUDE_PLUGIN_ROOT}/scripts/dae_progress.py <feature-dir>` and present its
output to the human — it shows where this checkpoint sits in the DAE pipeline.
The breadcrumb is advisory: a non-zero exit or a missing `progress.md` never
blocks the skill. Then create one TodoWrite todo per workflow step below. See
`${CLAUDE_PLUGIN_ROOT}/references/progress-indicator.md`.

### Step 1 — Run the check

Run `${CLAUDE_PLUGIN_ROOT}/scripts/dae_arch.py <methodology-root>` (add `--full`
for a whole-project audit). If it reports "no `architecture:` section", tell the
user the charter has no machine-readable architecture rules yet and stop.

### Step 1.5 — CRAP analysis

CP7 Light Verify is arch-check **plus** `crap-analyzer`. If crap-analyzer hasn't
run on the current diff, run it now over the feature's changed code. Keep its
summary for the handoff: max CRAP, the offenders over
`quality_thresholds.crap_max`, and the command. It is external and writes no
handoff of its own, so this is where CP8's refinement-advisor reads it.

### Step 2 — Present violations

Group the violations by kind (layering first — it is the architectural-vision
core). For each, show `file:line` and the rule. Do not auto-fix.

### Step 3 — Triage with the human

For each violation, the human decides: a real break (fix the code), or a rule
that no longer fits (amend `manifest.architecture` — and the charter prose).
`dae_arch.py` exiting non-zero means Checkpoint 7's architecture-fitness exit
criterion is unmet until the violations are resolved.

### Step 3.5 — Runbook gate (if runbook.md exists)

If `features/<slug>/runbook.md` exists, check that every step blocking a
deploy-related AC is `completed: true`. If any blocking step is open while
its dependent AC is asserting `met: true`, surface it as a verification
gap and refuse to mark CP7 complete. The runbook's `blocking_acs` list is
the source of truth — see `engineer/skills/plan/references/runbook-template.md`.

### Step 4 — Handoff

Emit a summary per `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md`.
`checkpoint: 7`; the `exit_criteria` block asserts the architecture-fitness
criterion with `verified_by: tool` and the `dae_arch.py` exit status as evidence,
and carries crap-analyzer's summary as a `crap_results` block (`max_crap`,
`offenders: [{symbol, file, crap, coverage}]`, `command`). CP8's harden and
refinement-advisor read that block.
`recommended_next`: "/engineer.harden (CP8)".

## References

- [Foundation Design](https://www.notion.so/3585ecdee0e2811bbc67ff4913c03207) —
  the `architecture:` manifest section (§2); the Checkpoint Exit Contract (§8)
