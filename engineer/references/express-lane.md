# Express lane — the XS weight, one pass, code-first

The small-feature lane. Same DAE tracking and deterministic gates as any feature,
but **one context, no born-die handoff chain, minimal docs** — the cheap end of
the `size` dial (`references/gate-profile.md`). It exists because the cost of a
feature is the per-checkpoint context re-prime and the doc artifacts, not the
code: a one-PR change should not pay for a five-artifact pipeline.

`size: XS` → `gate_profile: { front: auto, verify: light, lane: express }`.

## What it keeps (the DAE benefit)

- **Tracker row** — `feature-init` upserts a `TrackedFeature` exactly as it does
  for any feature. Traceability is never traded away for speed.
- **Branch hygiene**, one `features/NNN-slug/` folder, a PR.
- **Deterministic gates** — acceptance test + CRAP + `dae_ontology` + `dae_arch`.
  These are cheap scripts, not LLM burn; they stay.
- **The test IS the spec** — one Given/When/Then acceptance test stands in for
  `acs.md` + `spec.md` (mirrors prototype's "the prototype is the spec"). The
  behavior is pinned by the test, not by prose.

## What it collapses (the cost saving)

- **One context, no handoff chain.** A single born-die agent runs
  intake → implement → verify in one pass. No CP2→CP8 relay, so no per-checkpoint
  re-prime and no growing-context re-read across a chain — the dominant token
  sink on normal features.
- **Artifacts = code + test first.** No `acs.md`/`spec.md`/`plan.md`/
  `progress.md`/`session-log.md`. Just `feature.md` (the tracker contract) + the
  code + the test. A ≤5-line approach note in `feature.md` **only** if the diff
  is not self-evident.
- **No** multi-agent gauntlet, review-panel, or mutation (light verify).

## Code over docs — enforced

The express contract: **non-code doc chars must not exceed code chars.** An XS
feature whose Markdown outweighs its code has mis-scoped its ceremony. Surfaced
at the back gate (a `dae_mergeready` note / lint) — inform, don't block.

## Guardrails (safety wins, reusing existing rules)

- **Charter-flagged path** (payments, auth, migration, high blast-radius) →
  express is off the menu; the feature falls back to per-checkpoint review, same
  mechanic as `autonomy_level: low` suppressing `front: auto`
  (`references/gate-profile.md`). A tiny change to a flagged path is still
  reviewed.
- **Escalation ratchet (one-way up).** If the change turns out to be more than
  one PR mid-pass (decomposition trips, hidden coupling, the acceptance test
  won't close), express **promotes to full S/M** — create the missing
  `acs.md`/`spec.md`/`plan.md`, resume the normal pipeline, **keep the tracker
  row**. Never silently downgrades. A wrong-small projection self-corrects; a
  wrong-big one just spent a little more spec.

## Who reads it

- `feature-init` — `size: XS` derives this profile and runs the one-pass lane
  instead of scaffolding the CP2/CP3/CP4 handoffs.
- the back gate — `verify: light` + the code-over-doc note.
- `references/choice-points.md` — the projection that *recommends* XS.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/gate-profile.md` — the `size` dial XS extends
- `${CLAUDE_PLUGIN_ROOT}/references/choice-points.md` — how a feature is sized/pathed at the front
- `${CLAUDE_PLUGIN_ROOT}/references/two-paths.md` — the front-half (spec-first vs prototype-first) that feeds this weight
