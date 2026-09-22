---
name: express
description: Use to build an XS (express-lane) feature in one pass — intake→implement→verify in a single context, no handoff chain, code-first. Triggers — "/engineer.express", "express build", building a feature whose gate_profile.lane is express.
---

# express

The **express lane** for `size: XS` features (`${CLAUDE_PLUGIN_ROOT}/references/express-lane.md`).
One born-die agent runs **intake → implement → verify in a single context** — no
CP2→CP8 handoff chain, no sub-agents, no `acs.md`/`spec.md`/`plan.md`. The
acceptance test is the spec; docs stay capped below code. Same tracker row and
deterministic gates as any feature — just without the per-checkpoint re-prime
that dominates a normal feature's cost.

Runs *after* `feature-init` has created the `size: XS` feature (or a converged
prototype landed at `prototype_disposition: in-place`).

## When to use

- `feature-init` handed off a feature with `gate_profile.lane: express`.
- A converged XS prototype (`in-place`) — the prototype code is the starting
  implementation.

**Not for:** anything charter-flagged (payments/auth/migration/blast-radius),
`autonomy_level: low`, or bigger than ~1 PR — those take the full pipeline. If
you find yourself here on one of them, **escalate** (Step 5).

## Workflow

Do the whole thing in one context. **No sub-agents, no inter-phase handoffs.**

0. **Resolve + branch** — root + manifest via `${CLAUDE_PLUGIN_ROOT}/scripts/dae_resolve.py`;
   load `feature.md` + `CHARTER.md` (+ `prototype/` if `in-place`). Enforce branch
   hygiene via `${CLAUDE_PLUGIN_ROOT}/scripts/dae_branch.py`. **Re-check the
   guardrails** — charter-flagged or `autonomy_level: low` → stop, hand to the
   full pipeline (`discover-acs`); express is not for those.
1. **Pin behavior (test = spec)** — write **one** Given/When/Then acceptance test
   that defines done. If a prototype is the seed, reverse-engineer the test from
   what it demonstrates. This replaces `acs.md` + `spec.md`; do not write them.
2. **Implement to green** — build the minimum that passes the test. Code-first;
   the only prose allowed is a ≤5-line approach note in `feature.md`, and only if
   the diff is not self-evident. Prototype `in-place`: the prototype code *is* the
   start — clean it, don't rewrite.
3. **Verify (light)** — run the deterministic gates: the acceptance test + CRAP +
   `${CLAUDE_PLUGIN_ROOT}/scripts/dae_ontology.py` + `dae_arch`. LLM attention
   only on red. No mutation, no gauntlet, no review-panel.
4. **Code-over-doc check** — non-code doc chars must not exceed code chars for
   this feature; if they do, surface a one-line note (inform, don't block).
5. **Escalation ratchet (one-way up)** — if at any point the change is more than
   ~1 PR (decomposition trips, hidden coupling, the acceptance test won't close),
   **promote to full S/M**: write the missing `acs.md`/`spec.md`/`plan.md`, hand
   to `discover-acs`/`plan`, **keep the tracker row and branch**. Never downgrade
   silently.
6. **Land** — open the PR; update the tracker row via the driver
   (`references/tracker.md`). Back gate is `verify: light` — present it as a
   choice point (`${CLAUDE_PLUGIN_ROOT}/references/choice-points.md`): recommend
   merge on green gates, `autonomy_level`-dialed. Honor the external-write gate
   (PR merge is human unless `verify: auto` + `dae_mergeready` green).

## Handoff

Emit per `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md`. One handoff for
the whole lane (not one per phase) — **`checkpoint: null`**: express is *off the
numbered pipeline* (like `discuss`/`prototype`), so it carries no CP2→CP8 stop
and its deterministic gates — not an independent LLM reviewer — are the verifier
(the disjoint-verifier principle is satisfied by the scripts, and the numbered-
pipeline completeness checks do not apply to an XS feature). `recommended_next`:
"review the PR" (or auto-merge note if `verify: auto`). On escalation, the
feature *joins* the numbered pipeline — emit `status: escalated` naming what
tripped and pointing at `discover-acs` (CP2 onward).

## References

- `${CLAUDE_PLUGIN_ROOT}/references/express-lane.md` — the XS contract, guardrails, ratchet
- `${CLAUDE_PLUGIN_ROOT}/references/gate-profile.md` — the `size` dial (XS = this lane)
- `${CLAUDE_PLUGIN_ROOT}/references/choice-points.md` — the projection that sized it XS + the back-gate choice point
- Sister skills: `feature-init` (creates the XS feature), `discover-acs` (the escalation target), `prototype` (the `in-place` seed).
