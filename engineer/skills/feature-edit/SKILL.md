---
name: feature-edit
description: Use when an in-flight feature must change — scope shifts, an AC is refined, the plan evolves, a behavior is added or removed. Triggers — "/engineer.feature-edit", "change feature X to", "the ACs need updating", "revise the plan", "scope changed".
---

# feature-edit

Intent-driven editing of an in-flight feature. The human describes *what should now be true*; this skill figures out *which files and tools to touch* and orchestrates the change, including the downstream cascade.

The cascade-owning skill — `clarify` and `refine` deliberately stay single-artifact and route multi-artifact propagation here. Mixed mode: the agent proposes an edit plan, the human confirms before any write.

## When to use

Any time an existing feature's artifacts must change. `checkpoint: null`.

**Not for:** a brand-new capability (`discuss`); within-one-artifact ambiguity, no behavior change (`clarify`); validating consistency (`consistency-check`); cleaning up code (`refine`).

## Workflow

1. **Resolve + identify the feature** — resolve the methodology root + manifest via `${CLAUDE_PLUGIN_ROOT}/scripts/dae_resolve.py` (see `references/resolving.md`); locate the feature (slug, branch, or search `feature.md` titles/outcomes).
2. **Is this actually an edit?** — if the intent is a new capability or too big for one feature, surface it and redirect to `discuss`. Stop.
3. **Classify the entry artifact** — the highest-level artifact the intent directly changes: outcome/scope → `feature.md`; a behavior → `acs.md`; a GWT detail → `spec.md`; architecture/phasing → `plan.md`.
4. **Build the edit plan** — the cascade runs **strictly downstream** (`feature.md → acs.md → spec.md → plan.md`); upstream problems are surfaced, never auto-propagated. Per downstream artifact, classify by blast radius: small/mechanical → feature-edit edits directly; substantial → invoke the owning skill (`discover-acs` / `atdd:atdd` / `plan`) in edit-pass mode.
5. **Present the plan; human confirms** — show entry artifact, cascade, and how each step is handled. Nothing is written before confirmation.
6. **Execute** — in cascade order: direct edits and owning-skill invocations; regenerate `.build/spec.json` after any `spec.md` change; re-run affected test streams if code exists. If regeneration reveals an upstream problem, stop and surface it.
7. **Sync** — update `progress.md` (affected checkpoint rows) and the tracker via the driver. If the edit adds or changes a user-facing surface (route, command, screen), update that feature's row in the `verify-<app>` feature map (`${CLAUDE_PLUGIN_ROOT}/references/verify-app-skill.md`).
8. **Handoff** — emit a summary.

## Handoff

Emit per `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md`. `checkpoint: null`; `artifacts` lists every artifact edited. `recommended_next`: typically "re-run /engineer.consistency-check".

## References

- [Foundation Design](https://www.notion.so/3585ecdee0e2811bbc67ff4913c03207) — artifact schemas, the IR pipeline (Section 7)
- [Discuss & Upstream Funnel](https://www.notion.so/35a5ecdee0e281eaa35fced0c4e23384) — when an "edit" is really a new feature
