---
name: refine
description: Use after a feature's code is implemented and passing, to clean up the changed code before verification. Triggers — "/engineer.refine", "refine this code", "clean up the feature", "refactor what we built".
---

# refine

Charter-bound clean-up of a feature's changed code — Checkpoint 6. Modeled on Claude Code's stock `/simplify` (a three-subagent parallel review) with two layers the stock skill lacks: **charter validation** of every proposal, and **graceful breaking changes**.

The behavior contract (ACs + specs) is sacred — a refactor that breaks it is a category error. New shapes are introduced alongside old, never instead of.

## When to use

Checkpoint 6, after `atdd:atdd-team` produces passing code, before `crap-analyzer` (Checkpoint 7).

**Verification independence:** if `manifest.verification.apply_to_checkpoints` includes `6`, refine must run on a non-implementer agent. The three review subagents (Step 2) are fresh regardless, so independence is satisfied by construction.

**Not for:** changing behavior (`feature-edit`); risk analysis (`crap-analyzer`); code that isn't implemented/green yet.

## Workflow

**Step 0 — Entry gate.** Before starting, verify the prior checkpoint is complete: run `${CLAUDE_PLUGIN_ROOT}/scripts/dae_handoff.py <feature-dir> --through 5`. On a non-zero exit, **stop** and surface the gap to the human — do not proceed.

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

1. **Resolve + scope** — resolve the methodology root + manifest via `${CLAUDE_PLUGIN_ROOT}/scripts/dae_resolve.py` (see `references/resolving.md`); locate the feature. Scope = the feature branch's changed code (`git diff` against the branch point). Load `feature.md`, `acs.md`, `spec.md`, `CHARTER.md`.
2. **Dispatch three parallel review subagents** (`superpowers:dispatching-parallel-agents`), each over the same changed code. Before dispatching, run `${CLAUDE_PLUGIN_ROOT}/scripts/dae_dup.py <methodology-root>` to get deterministic project-wide duplicate findings; pass the JSON result into the **Reuse** subagent's context as a tool input (the subagent treats it as one signal alongside its own LLM judgment, and produces a unified set of findings — not a separate list). If `dae_dup.py` returns anything other than `status: ok` — `status: unavailable` (the backend tool isn't installed), `status: skipped` (manifest `duplication.skip: true`), `status: unsupported` (the configured backend isn't implemented in this version), or `status: error` (scan failed) — surface that status in the Reuse subagent's prompt and proceed with its existing LLM-only judgment.
   - **Reuse** — duplication (LLM + `dae_dup.py` findings), reinvented wheels, dead code, missed existing utilities. **LSP-first lookup** — at dispatch time, check whether an LSP MCP capability is available; pass that detection result and the LSP-first preference into the Reuse subagent's prompt so it uses find-references / workspace-symbols when available, with graceful fallback to grep + Read. See `${CLAUDE_PLUGIN_ROOT}/references/code-lookup.md`.
   - **Quality** — clarity, structure, naming, incidental complexity, maintainability
   - **Efficiency** — redundant computation, repeated lookups, visible performance smells
3. **Consolidate** — merge findings; dedup overlaps (note multi-lens hits as strong signals); keep genuine conflicts as alternatives for the human.
4. **Charter filter** — check every proposal against `CHARTER.md` (architecture, conventions, methodology, the ACs+specs contract). Charter-violating proposals are **rejected internally — never shown**. This filter is the DAE-specific layer the stock skill lacks.
5. **Classify breaking changes** — consumer-facing (something outside the blast radius depends on the old shape) → graceful path: deprecation-marked forwarding shim + migration note, new shape alongside old. Internal-only → hard change is fine.
6. **Present; human picks** — show charter-compliant proposals (change, why, blast radius, churn). The human selects which are worth the churn.
7. **Apply** — apply selected; install graceful paths where needed; re-run both test streams. Before running the test streams, ensure required infra is up: read `manifest.yml`'s `infra:` section, then call `${CLAUDE_PLUGIN_ROOT}/scripts/dae_infra.py ensure <names>` for each declared dependency the tests need. On a `start-failed` structured failure → stop and surface the diagnosis. On a missing manifest declaration for required infra → stop with the "declare in manifest" message. Any failure → revert that proposal and report.
8. **Handoff** — emit a summary.

If a charter rule itself blocks a genuinely better design, surface it in the handoff (→ `feature-edit` / charter amendment). refine does not amend the charter.

## Handoff

Emit per `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md`. `agent_id` must differ from the implementer if checkpoint 6 is independence-gated. `checkpoint: 6`; `recommended_next`: "/engineer.arch-check (CP7 Light Verify; it runs crap-analyzer too)".

The handoff MUST include the `exit_criteria` block asserting each of Checkpoint 6's exit criteria (Foundation Design Section 8) with `verified_by`, `met`, and `evidence`. For `verified_by: tool` criteria, the evidence MUST be the tool's actual output. The checkpoint is marked done only when every criterion is met.

**Before stopping**, apply the dispatch rule — see `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md`. CP7 verify needs a fresh agent (charter §6); a subagent dispatched via the Agent tool satisfies that. Do **not** ask the human "want me to dispatch?" — auto-dispatch at autonomy `medium`/`high`; confirm-then-dispatch at `low`. If verify needs resources you can't reach (live emulators, prod creds), write the exact dispatch command in the handoff and stop.

## References

- `superpowers:dispatching-parallel-agents` — the Step 2 dispatch pattern
- `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md` — when to dispatch vs stop
- [Foundation Design](https://www.notion.so/3585ecdee0e2811bbc67ff4913c03207) — charter format, verification independence
- `engineer/references/handoff-dispatch.md` — infra-ensure-before-stop rule
