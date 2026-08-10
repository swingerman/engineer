---
name: atdd-team
description: >-
  Use to orchestrate a team-based ATDD workflow — six phases (spec writing,
  spec review, pipeline generation, implementation, refine, verify & harden)
  each handled by a fresh agent so no role erodes across a long-running
  feature. Triggers — "build a feature with a team", "use ATDD with agents",
  "create an ATDD team", "orchestrate agents for ATDD", "coordinate agents
  for feature development", "add ATDD roles to my team", "add spec-writer
  and reviewer to the team".
---

# Team-Based ATDD Workflow

Orchestrate an agent team that follows the Acceptance Test Driven Development
workflow. The team lead coordinates specialist agents through six phases. Each
phase is run by a **fresh agent invocation** — no agent persists across phases.

## Why fresh per phase

A long-lived agent's context compacts as a feature runs for hours. Compaction
silently erodes role identity and discipline: agents lose their role, invent
constraints that do not exist, and skip expensive-but-required steps. A fresh
per-phase agent reloads its instructions clean — the same insight as the
engineer plugin's per-skill model. The "team" exists for **parallelism** across
features, not for keeping agents alive within one feature.

## Team Detection

Before spawning phase agents, check for existing teams:

1. Read `~/.claude/teams/` to list active teams.
2. If a team exists, present the user with a choice:
   - **Extend** — run the ATDD phases for this feature alongside the existing team.
   - **Replace** — shut down the existing team and run ATDD fresh.
   - **New team** — run the ATDD pipeline as a separate team.

If no team exists, proceed directly.

## Roles

Each phase is run by a fresh agent invocation scoped to that phase, then ended.

| Role | Maps to | Owns phase |
|------|---------|-----------|
| `spec-writer` | discuss, discover-acs, atdd spec step | 1 Spec Writing |
| `reviewer` | spec-guardian agent | 2 Spec Review |
| `implementer` | atdd impl, pipeline-builder | 3 Pipeline Gen, 4 Implementation |
| `refiner` | the engineer plugin's `refine` skill | 5 Refine |
| `architect` | consistency-check, crap-analyzer, atdd-mutate | 6 Verify & Harden |

The **team lead** (the orchestrating agent or user) owns the workflow, approves
all work, enforces discipline, and verifies the `agent_id` independence binding.
The team lead never delegates approval — specs are the team lead's contract.

## Coordination rules

- **Durable handoffs, not chat.** Each phase ends by writing a handoff summary
  to `features/NNN-slug/handoffs/` (the engineer plugin's handoff contract, with
  the `exit_criteria` block). The next phase's fresh agent reads the prior
  handoff for context — coordination survives a context compaction.
- **Phase gate = checkpoint exit criteria.** A phase is done only when its
  handoff asserts every exit criterion met (Foundation Design Section 8). Before
  starting a phase, verify the prior checkpoint is complete — run the engineer
  plugin's `scripts/dae_handoff.py <feature-dir> --through <prior-cp>`.
- **`agent_id` independence (Principle 7).** Each phase handoff records its
  `agent_id`. The `architect`'s `agent_id` MUST differ from both the
  `implementer`'s and the `refiner`'s — the verifier verifies neither its own
  code nor its own refinement. The team lead checks this.
- **Role boundary.** The `implementer` takes the code to green only — it does
  NOT do deep refactoring; that is the `refiner`'s phase. Every phase handoff
  states explicitly what was NOT done and what is left for the next role.
- **Per-phase anchor.** Each phase agent's spawn prompt embeds a `reorient`-style
  anchor: role, autonomy level, the prior handoff, the phase's exit criteria,
  and the non-negotiables. See `references/prompts.md`.

## Workflow Phases

Execute phases strictly in order. Each phase spawns a fresh agent, ends with a
durable handoff, and is gated on the prior checkpoint's exit criteria.

Before Phase 1, create one TodoWrite todo per phase of this workflow
(Phases 1–6), all at once — the full list up front, as a roadmap. Flip each
todo to `in_progress` / `completed` as you go. See
`${CLAUDE_PLUGIN_ROOT}/references/progress-indicator.md`.

### Phase 1 — Spec Writing

**Assign to:** a fresh `spec-writer` agent.

Instruct it to:
1. Read the existing codebase to understand domain language
2. Write the feature's `spec.md` in standard Gherkin
3. Use ONLY external observables — no implementation language
4. Follow the standard Gherkin format from the atdd skill
5. End with a handoff summary

**Gate:** Team lead reviews and approves the specs (Checkpoint 3 exit criteria).
Do not proceed until approved.

For the detailed prompt template, see `references/prompts.md` — Phase 1.

### Phase 2 — Spec Review

**Assign to:** a fresh `reviewer` agent.

Run the spec-guardian agent to audit `spec.md` for implementation leakage:
class/function names, database tables, API endpoints, framework terms, internal
state. Also verify one behavior per scenario and clarity for non-developers.

**Gate:** The reviewer's handoff reports findings. The team lead decides whether
the spec needs revision. If revisions are needed, return to Phase 1.

For the detailed prompt template, see `references/prompts.md` — Phase 2.

### Phase 3 — Pipeline Generation

**Assign to:** a fresh `implementer` agent (or the team lead).

Generate the project-specific test pipeline — the `pipeline-builder` agent
produces the generator + step handlers + runner; `dae_gherkin.py` is the
portable, shipped parser. Run the acceptance tests — they **must fail** (red).
If they pass, either the behavior exists or the generator is wrong.

**Gate:** Acceptance tests fail as expected. Pipeline is functional.

For the detailed prompt template, see `references/prompts.md` — Phase 3.

### Phase 4 — Implementation

**Assign to:** a fresh `implementer` agent.

Instruct it to:
1. Run acceptance tests — confirm they fail
2. Pick the simplest failing acceptance test
3. Write a unit test, then minimal code to pass it
4. Refactor in-the-small, repeat until that acceptance test passes
5. Move to the next failing acceptance test
6. Continue until ALL acceptance + unit tests pass

**Rules for the implementer:**
- Never modify `spec.md` — it is the contract
- Never modify generated test files — only regenerate
- Take the code to green only — deep refactoring is the `refiner`'s phase
- If a spec seems wrong, stop and ask the team lead
- **Run rounds without asking.** The failing tests are the bar; a round is
  "pick the next failing test, close it, re-run". Do not pause between rounds
  to report progress or ask whether to continue — that pause is the babysitting
  the checkpoint exists to avoid. Escalate to the team lead only on: a spec that
  looks wrong, a green test turning red, or `manifest.autonomy.stuck_loop_threshold`
  consecutive rounds with no test moving to green.

**Then — the gauntlet, if the feature declared a bar.** Once both streams are
green, read `plan.md`'s Test strategy for a `gauntlet:` block. If there is one,
loop a **fresh critic** against it: capture the candidate with the declared
`capture:` command, A/B it against the bar, take the single largest gap back to
the implementer, repeat until the critic returns `ties-or-wins` or a stop
condition fires (`max_rounds`, two identical gaps, or a test stream regressing).
This is what grades the things Gherkin cannot — visual fidelity to a ready
design, output quality — instead of handing that grading back to the team lead
one screenshot at a time. Critics are **plain subagents, never forks** (they
re-run on their own captured output; a fork self-perpetuates). Record every
round as `gauntlet_rounds[]` in the handoff. **No `gauntlet:` block → no loop,
silently.** Full contract: the engineer plugin's `references/gauntlet.md`.

**Gate:** Both test streams green (Checkpoint 5 exit criteria), and — when a bar
was declared — the gauntlet stopped on `clear`. A gauntlet that stopped on
`cap` / `no-progress` / `regression` hands off with `human_action_needed: yes`
and the open gap named; the team lead decides whether to accept it or push.

For the detailed prompt template, see `references/prompts.md` — Phase 4.

### Phase 5 — Refine

**Assign to:** a fresh `refiner` agent.

After both test streams are green, the refiner runs the engineer plugin's
`refine` skill — the post-green code-improvement pass (reuse, quality, and
efficiency lenses; every proposal charter-filtered). This is the dedicated
improvement pass that the implementer does NOT do inline.

**Gate:** Checkpoint 6 exit criteria — refine ran, both streams still green,
charter filter applied to every proposal.

For the detailed prompt template, see `references/prompts.md` — Phase 5.

### Phase 6 — Verify & Harden

**Assign to:** a fresh `architect` agent — `agent_id` MUST differ from the
implementer's and the refiner's.

Independent verification and hardening:
1. `consistency-check` — artifacts agree
2. `crap-analyzer` — CRAP + coverage (Checkpoint 7)
3. mutation testing — **driven by the charter's mutation policy**, not agent
   discretion. If the charter mandates mutation, it runs; the architect does
   not get to skip it because it is slow. (Checkpoint 8)

**Gate:** Checkpoints 7 + 8 exit criteria met.

For the detailed prompt template, see `references/prompts.md` — Phase 6.

## After Completion

When all phases pass:

1. Run both test streams one final time to confirm green
2. Ask the user whether to commit (do not auto-commit)
3. Ask whether to iterate with the next feature (return to Phase 1) or stop
4. **Team teardown.** When the feature reaches CP8 (Harden complete) or its PR is merged, propose deleting the `atdd-<slug>` team. Teams are per-feature scaffolding — leaving them alive after the feature ships clutters the team list and wastes context on every `next` survey (nexthq saw a team idle for 5 days post-feature). At autonomy `high`, run `TeamDelete` and report. At `medium`, run + report. At `low`, surface the proposal and wait. If the feature is still in flight (e.g. follow-up bugs likely), the user can defer.

## Lifecycle

- **Create**: at the start of Phase 1 if a team for this feature doesn't already exist.
- **Reuse**: a session-resume on the same feature finds the existing team and reuses it.
- **Teardown**: at "After Completion" Step 4 (CP8 done / PR merged). `engineer:progress-log` may also trigger teardown when it observes a feature advance to `status: done`.

## Tips for Team Leads

- **Never delegate spec approval.** Specs are the team lead's contract.
- **Each phase is a fresh agent.** Do not keep one agent alive across phases —
  that is the erosion the per-phase model exists to prevent.
- **Verify the `agent_id` binding.** The architect must not be the implementer
  or the refiner — verification independence (Principle 7).
- **Read the handoff, not the chat.** A phase's durable handoff is the input to
  the next phase; it survives a compaction, a chat message does not.
- **Scope tightly.** One feature per pipeline. Do not spec the whole system.

## Additional Resources

### Reference Files

For detailed prompt templates for each phase:
- **`references/prompts.md`** — per-phase agent spawn prompts, each with the
  anchor block and the handoff-ending instruction.
