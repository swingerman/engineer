---
name: plan
description: Use when a feature has ACs and specs and needs an architecture plan before implementation. Triggers — "/engineer.plan", "plan this feature", "plan the implementation", "design the architecture".
---

# plan

Produce a feature's architecture plan — Checkpoint 4, the most consequential architectural checkpoint. Where engineering authority over **code design** and **performance** is exercised: the agent proposes, the human decides.

Mixed mode — the agent proposes the architecture, the human confirms it, then the rest of the plan is drafted.

## When to use

After `discover-acs` (Checkpoint 2) and `atdd:atdd` (Checkpoint 3). Produces `plan.md`.

If `spec.md` is missing, warn — planning should follow spec formalization — but the user may override and plan from `acs.md` alone (flag the skipped step in the handoff).

**Not for:** Given/When/Then specs (`atdd:atdd`); small changes to an existing plan (`feature-edit`).

## Workflow

**Step 0 — Entry gate.** Before starting, verify the prior checkpoint is complete: run `${CLAUDE_PLUGIN_ROOT}/scripts/dae_handoff.py <feature-dir> --through 3`. On a non-zero exit, **stop** and surface the gap to the human — do not proceed.

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

1. **Resolve + load** — resolve the methodology root + manifest via `${CLAUDE_PLUGIN_ROOT}/scripts/dae_resolve.py` (see `references/resolving.md`); load `feature.md`, `acs.md`, `spec.md`, `CHARTER.md`.
2. **Propose the architecture** — draft only the Architecture section (components, data flow, where new code lives, coupling, key decisions + rationale + alternatives). **Pin cross-track interface contracts:** for any interface shared across parallel implementation tracks (a client and a backend built concurrently, two services, etc.), specify the exact wire contract — field names, casing, JSON shape, status codes — not a prose sketch or ASCII diagram. A loose contract forces the other track to reverse-engineer and guess (wsapi `/auth/firebase` was left as `{idToken}` with no casing; the parallel client shipped a snake_case guess that had to be reconciled later). This is the interface-pinning that makes parallel tracks safe — see `${CLAUDE_PLUGIN_ROOT}/references/parallelism.md`. Ground it in the actual code: prefer LSP — `workspaceSymbol` to locate the components you'll touch, call-hierarchy (`incomingCalls`/`outgoingCalls`) to map coupling and blast radius, `findReferences` before proposing a change to a shared symbol — over grep, when an LSP MCP capability is available; fall back to grep + Read otherwise (see `${CLAUDE_PLUGIN_ROOT}/references/code-lookup.md`). Present it; iterate until the human confirms. Do not draft the rest until then. **Gate-profile branch** (see `${CLAUDE_PLUGIN_ROOT}/references/gate-profile.md`): the mid-way "iterate until the human confirms" stop applies when the feature's `gate_profile` is **absent**, **or** when `autonomy_level` is **`low`** (`low` suppresses front-dialing — the human reviews everything). Under `front: bundled` or `auto` **at `medium`/`high`**, do **not** stop here — draft the architecture and the rest in one pass; the architecture is approved with the bundle at Step 6 (`bundled`) or trusted to the gauntlet + back gate (`auto`). Architecture stays a human decision under `bundled`; only *when* it's approved changes.
3. **Draft the rest** — draft the remaining sections. When `gate_profile` is absent, the human confirms Step 2's architecture first, then reviews the finished file. Under `bundled`/`auto`, draft straight through. Let `gate_profile.verify` set the Test strategy's back-gate depth: `heavy` → an explicit human validation step named in `validation_method`; `light` → lean on the objective gates (acceptance + CRAP + mutation + gauntlet) and say so.
4. **Charter Check** — validate the plan against `CHARTER.md`. Produce the two-part structured check: a compliance table (one row per charter rule, plus auto-rows for autonomy stance, verification independence, mutation policy, and — at high autonomy — performance budgets), and an Amendments section. **Hard rule:** never finish a plan with a ⚠️ deviation that lacks a matching amendment ADR. Either write the amendment inline, or stop and emit a handoff with `human_action_needed: decision`.
5. **Write `plan.md`** — frontmatter (`slug`, `checkpoint: 4`, `plan_status`, `created`) + sections: Architecture, Charter Check, Phasing, Performance budgets, Collaboration schedule, Execution modes, Test strategy. **Test strategy** must explicitly incorporate `feature.md`'s `validation_method` if it carries a non-default value — e.g. if `validation_method` is "canary 5% prod for 24h, watch dashboard X," the Test strategy section names the canary phase, the dashboard, and the rollback trigger. If `validation_method` is absent, default to the standard DAE stack (acceptance + unit + mutation per charter) and say so explicitly. **Declare the gauntlet bar** in Test strategy when the feature has something to build *against* that the tests can't assert — a design export, a reference UI screenshot or URL, a reference implementation, a golden output. Emit the `gauntlet:` block (bar paths + `capture:` command + `max_rounds`) per `${CLAUDE_PLUGIN_ROOT}/references/gauntlet.md`; CP5 loops builder↔critic against it after green instead of handing the grading back to the human. No such reference exists → omit the block entirely; the absence *is* the opt-out and no gauntlet runs. A bar must be inspectable — never write prose ("matches the design system") or the ACs into it. **A promoted prototype is the bar by default:** if `feature.md` carries a `prototype:` path (from the `prototype` skill), declare that path as the `gauntlet:` bar automatically, with a `capture:` that renders/runs the candidate in the same form — the prototype *is* iteration 0's reference, no separate bar needed.
6. **Review panel** — dispatch the standing adviser + advocate pair against `plan.md` per `${CLAUDE_PLUGIN_ROOT}/references/review-panel.md`. This is the last gate before code exists, and a plan resting on a false premise is the most expensive thing to discover at CP5 — one ei-theme plan's *central* factual claim about a shared template turned out to be wrong, and only the advocate caught it. Give both briefs the source files the Architecture section makes claims about, not just the artifacts. Autonomy-keyed; skip silently when the plan is a one-module addition with no architectural argument. Fold the findings into `plan.md`, then record every finding — accepted or rejected — as `panel_findings[]` in the handoff. An unaddressed `error`-severity finding blocks the CP5 dispatch.
7. **Generate `runbook.md` if the plan touches infra/operator steps** — provisioning (cloud project create, billing link, API enablement), secrets management, console-only configuration, manual DNS, deploy-day toggles. Use `references/runbook-template.md`. Each step has `[ ] human` or `[ ] agent` ownership, optional `command:` if runnable, and `evidence:` for completion. Deploy-related ACs (e.g. "site loads at staging URL") MUST NOT claim green until the runbook's prerequisite steps are checked off. If the plan has no infra/operator surface, skip — no empty file.
8. **Handoff** — emit a summary.

`plan.md` has **phasing (stages/slices), not a task list** — tasks emerge from specs (one spec = one TDD cycle), driven by `atdd:atdd-team`.

## Handoff

Emit per `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md`. `checkpoint: 4`; `recommended_next`: "/atdd:atdd-team to implement against the specs". If a deviation needs a decision, `human_action_needed: yes` (decision).

The handoff MUST include the `exit_criteria` block asserting each of Checkpoint 4's exit criteria (Foundation Design Section 8) with `verified_by`, `met`, and `evidence`. For `verified_by: tool` criteria, the evidence MUST be the tool's actual output. The checkpoint is marked done only when every criterion is met.

**The front gate.** Under `gate_profile.front: bundled` (see `${CLAUDE_PLUGIN_ROOT}/references/gate-profile.md`), CP4 is where the human's *one* front decision lands: present `acs.md` + `spec.md` + `plan.md` **together** for a single approval before CP5 — this is the bundled front gate that replaces the separate CP2 AC stop and mid-CP4 architecture stop. On approval, dispatch CP5. Under `front: auto`, skip the front gate and dispatch CP5 directly (the back gate + gauntlet carry it). When `gate_profile` is absent — **or `autonomy_level` is `low`** — there is no bundle; the per-checkpoint approvals (Step 2 architecture confirm, CP2 AC stop) already happened.

**Before stopping**, apply the dispatch rule — see `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md`. CP5 implement is a different role than planner; auto-dispatch the implementer subagent at autonomy `medium`/`high`; confirm-then-dispatch at `low`. Skip dispatch only if the plan emitted `human_action_needed: yes` (decision pending, including an unaddressed `error`-severity panel finding) — in that case stop until the human resolves.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md` — when to dispatch vs stop
- `${CLAUDE_PLUGIN_ROOT}/references/review-panel.md` — the Step 6 adviser + advocate gate
- [Foundation Design](https://www.notion.so/3585ecdee0e2811bbc67ff4913c03207) — the structured Charter Check (Section 3)
- The DAE methodology page — execution model, autonomy levels, collaboration schedule
