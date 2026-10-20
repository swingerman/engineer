---
name: atdd
description: Use to write a feature's acceptance specs and generate its test pipeline — Checkpoint 3 of the DAE pipeline. The engineer-namespace entry point into the atdd plugin's acceptance workflow. Triggers — "/engineer.atdd", "write the spec", "Checkpoint 3", "formalize the ACs as specs", "generate the test pipeline".
---

# atdd

The DAE pipeline's Checkpoint 3 (Spec) entry point. AC discovery (Checkpoint 2,
`discover-acs`) decided *what behaviors must work*; this step formalizes them as
a standard-Gherkin `spec.md` and generates the project-specific test pipeline.

This skill is a **thin bridge**: the acceptance workflow itself lives in the
`atdd` plugin (`atdd:atdd`). `engineer.atdd` wraps it with the DAE checkpoint
contract — the entry gate in, the handoff out — so the acceptance pipeline is a
first-class checkpoint of the engineer pipeline rather than a separate detour.

**Requires the `atdd` plugin.** If it is not installed, tell the user to run
`/plugin install atdd@disciplined-agentic-engineering` and stop.

## When to use

Checkpoint 3, after `discover-acs` (Checkpoint 2) has produced an approved
`acs.md`. Produces `spec.md` + the feature's `.build/` pipeline.

**Not for:** AC discovery (`discover-acs`); planning (`plan`); using the
acceptance workflow outside a DAE feature folder (invoke `atdd:atdd` directly).

## Workflow

### Step 0 — Entry gate

Verify the prior checkpoint is complete: run
`${CLAUDE_PLUGIN_ROOT}/scripts/dae_handoff.py <feature-dir> --through 2`. On a
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

### Step 1 — Run the acceptance workflow

Invoke the `atdd:atdd` skill, scoped to this feature: write the feature's
`spec.md` in standard Gherkin from `acs.md`, then generate the test pipeline
(the `pipeline-builder` agent + the portable `dae_gherkin.py` parser). Present
`spec.md` to the human for approval — specs are the human's contract.

If the harness seeds a DB and `manifest.acceptance.fixture_parity.check` is set,
require the generated pipeline to run that check as a **pre-run gate** (fail loud
on fixture↔schema drift, before the acceptance tests), so drift can't fake a RED
cliff or mask a real defect. See `${CLAUDE_PLUGIN_ROOT}/references/fixture-parity.md`
— the robust fix (boot the test DB from canonical schema + migrations) belongs in
the `pipeline-builder`, which this skill bridges to.

If the generated CI runner needs `dae_gherkin.py` (it lives only in the
version-pinned plugin cache and is absent in CI), vendor it into the project
**with a drift check** rather than a bare copy that silently goes stale on a
plugin bump: record `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dae_gherkin.py --fingerprint`
at vendor time and have CI assert the vendored copy's `--fingerprint` still matches
it, failing loud on drift. (The robust fix — a pip-installable parser — also lives
in the `pipeline-builder`.)

### Step 2 — Handoff

Emit a summary per `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md`.
`checkpoint: 3`; the `exit_criteria` block asserts Checkpoint 3's criteria
(Foundation Design Section 8) — `spec.md` parses to a valid IR, every AC maps to
≥1 scenario, spec-check passes — each with `verified_by` and evidence.
`recommended_next`: "/engineer.plan".

### Step 3 — Dispatch the next checkpoint

`spec.md` is the human's contract and gets human approval in Step 1. Once
approved, **auto-dispatch /engineer.plan** at autonomy `medium`/`high`;
confirm-then-dispatch at `low`. See
`${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md`. Don't bounce the
mechanical "ready to plan?" question back to the human after they already
approved the spec.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/plain-prose.md`: write every artifact this skill produces to these rules
- `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md` — when to dispatch vs stop
- [Foundation Design](https://www.notion.so/3585ecdee0e2811bbc67ff4913c03207) —
  the Checkpoint Exit Contract (Section 8)
- `atdd:atdd` — the acceptance workflow this skill bridges to
