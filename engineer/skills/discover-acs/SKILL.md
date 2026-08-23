---
name: discover-acs
description: Use when a Ready feature needs its acceptance criteria discovered before specs are written. Triggers — "/engineer.discover-acs", "/engineer.acceptance-criteria", "discover ACs", "what must this feature do", "figure out acceptance criteria".
---

# discover-acs

Discover a feature's acceptance criteria — Checkpoint 2. ACs are **decisions about what behaviors must work**, in **domain language**. They precede the Given/When/Then formalization that `atdd:atdd` produces.

Separating AC discovery (divergent decisions) from spec formalization (convergent encoding) is what protects domain language from leaking into implementation language.

## When to use

On a feature with `autonomy_level` set and `status` of `ready` (greenfield) or `in-progress`/`done` (onboarded existing work). Produces `acs.md`.

**Two modes:**
- **Greenfield** — `status: ready`, no existing spec. Discover ACs from scratch via the four-pass interview.
- **Reverse-engineer** — onboarded feature (`in-progress`/`done`) that already has a spec (a Speckit `spec.md`, a design doc, shipped code). Extract candidate ACs from the existing material, then interview only for the gaps it leaves.

**Not for:** a parked feature (`discuss` to promote first); a feature that already has a complete `acs.md` (`feature-edit`); producing Given/When/Then specs (`atdd:atdd`); deciding whether to build the feature (`discuss`).

## Workflow

**Step 0 — Entry gate.** Before starting, verify the prior checkpoint is complete: run `${CLAUDE_PLUGIN_ROOT}/scripts/dae_handoff.py <feature-dir> --through 1.5`. On a non-zero exit, **stop** and surface the gap to the human — do not proceed.

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

1. **Resolve + validate** — resolve the methodology root + manifest via `${CLAUDE_PLUGIN_ROOT}/scripts/dae_resolve.py` (see `references/resolving.md`); locate the feature. Reject if not found, if `status: parked` (→ `discuss` to promote first), or if `acs.md` already exists with content. Pick the mode: existing spec/code present → reverse-engineer; else → greenfield.
2. **Load** — `feature.md`, `CHARTER.md`, `manifest.yml`, prior `handoffs/`. Reverse-engineer mode: also load the existing spec / design doc / relevant code. **For code lookup in reverse-engineer mode** (surveying what exists, tracing what calls what), prefer LSP workspace-symbols / find-references when an LSP MCP capability is available; fall back to grep + Read otherwise. See `${CLAUDE_PLUGIN_ROOT}/references/code-lookup.md`.
3. **Discover the ACs:**
   - **Greenfield** — interview in four passes, one question per turn, coverage prompts per pass.
   - **Reverse-engineer** — extract candidate ACs from the existing material, organized by the four passes; then interview only for genuine gaps the material leaves undecided. Gap questions may be **batched** (e.g. one `AskUserQuestion` with up to 4) rather than one-per-turn — the existing material already carries the bulk.

   The four passes:
   - **Happy path** — the core journey, every behavior when all goes right
   - **Edge cases** — empty / extreme / boundary / concurrency / partial state
   - **Errors & security** — missing/malformed input, authorization, external failure, abuse
   - **Cross-cutting** — audit, observability, idempotency, data lifecycle, performance

   **3b. Domain coverage checklists (MANDATORY pass).** After the four interview passes, scan `feature.md`'s outcome and scope for surface signals and consult any matching checklist in `${CLAUDE_PLUGIN_ROOT}/references/ac-coverage/`:

   | Signal phrase / keyword | Checklist file |
   |---|---|
   | public web page, site, marketing, HTML output | `web-seo.md` |
   | login, OAuth, auth, session, token, SSO | `auth-oauth.md` |
   | deploy, staging, production, infra, hosting, CI/CD | `deploy-model.md` |
   | UI component / page targeting humans | `accessibility.md` (when written) |
   | schema change, data backfill, migration, rename column | `data-migration.md` (when written) |

   For each matched checklist: present its items as a single batched `AskUserQuestion` (multi-select) with the file's content as the option list. The human ticks "yes, this matters" / "no, out of scope" per item. Each ticked item becomes an AC candidate in Step 6/7. The checklists do **not** auto-create ACs without confirmation. image-titler shipped without a default `og:image` AC because nothing prompted the question — these checklists fix that class of gap.

4. **Enforce domain language** — when implementation leaks in ("returns 401", "the endpoint", table/class names), soft-warn and rephrase to the user-observable behavior; user confirms. Don't block — educate.
5. **Handle scope drift** — if a behavior surfaces outside `feature.md`'s outcome, offer three options: broaden `feature.md`, drop as out-of-scope, or park a separate `discuss`. User picks.
6. **Coverage check** — before writing, report ACs captured + which passes were covered; if a pass was skipped, prompt once.
7. **Write `acs.md`** — YAML frontmatter (`ac_count`, `high_priority_count`, `discovered`) + numbered `## AC-N: <name>` sections, each with `Priority`, `Type`, and a domain-language body.
8. **Review panel** — dispatch the standing adviser + advocate pair against `acs.md` per `${CLAUDE_PLUGIN_ROOT}/references/review-panel.md`. This is the cheapest place in the pipeline to catch a wrong AC: `atdd` formalizes these into executable specs next, and everything downstream is derived from them. Autonomy-keyed (offer at `low`, auto at `medium`/`high`); skip silently on a trivial AC set. In **reverse-engineer mode** add the reverse-engineering clause to both briefs — an AC read back off working code is the exact case where unfalsifiable and merely-descriptive ACs slip through. Fold the findings into `acs.md`, then record every finding — accepted or rejected — as `panel_findings[]` in the handoff.
9. **Handoff** — emit a summary.

Re-invoking on a feature with existing `acs.md` is an edit pass (preserve AC IDs). Big restructures → `feature-edit`.

In reverse-engineer mode, note in the handoff that `acs.md` and the original spec should later be reconciled — a good `consistency-check` target.

## Handoff

Emit per `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md`. `checkpoint: 2`; `human_action_needed: yes` (review); `recommended_next`: "/engineer.atdd to formalize as Given/When/Then specs" (greenfield), or "/engineer.consistency-check to reconcile acs.md against the existing spec" (reverse-engineer).

The handoff MUST include the `exit_criteria` block asserting each of Checkpoint 2's exit criteria (Foundation Design Section 8) with `verified_by`, `met`, and `evidence`. For `verified_by: tool` criteria, the evidence MUST be the tool's actual output. The checkpoint is marked done only when every criterion is met.

ACs ship with `human_action_needed: yes` (the human owns the AC contract) — so this checkpoint is one of the explicit stop points per `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md`. Present the ACs for review; do **not** auto-dispatch CP3 atdd until the human has approved them.

**Unless the feature's `gate_profile.front` says otherwise, and only at `autonomy_level` `medium`/`high`** (see `${CLAUDE_PLUGIN_ROOT}/references/gate-profile.md`): under `front: bundled` or `auto`, the AC contract is not approved *here* — it is approved as part of the one **front bundle** at CP4 (`bundled`), or trusted to the back gate (`auto`). In those cases set `human_action_needed: no`, note `front_gate: deferred` in the handoff, and auto-dispatch CP3. Only when `gate_profile` is **absent** — or when `autonomy_level` is **`low`** (which suppresses front-dialing; the human is reviewing everything anyway) — does the standalone AC stop above apply. That is the backward-compatible / safety default.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md` — when to dispatch vs stop
- `${CLAUDE_PLUGIN_ROOT}/references/review-panel.md` — the Step 8 adviser + advocate gate
- `${CLAUDE_PLUGIN_ROOT}/references/ac-coverage/README.md` — index of domain-aware coverage checklists
- [Foundation Design](https://www.notion.so/3585ecdee0e2811bbc67ff4913c03207) — feature.md schema
- The DAE methodology page — why ACs and specs are separate
