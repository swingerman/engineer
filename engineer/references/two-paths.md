# Two paths, one destination — spec-first and prototype-first

A feature can reach the **same** fully-specced, hardened end state by two routes.
They differ only in the **front half** — which they front-load. The back half
(refine → verify → harden) is identical discipline in both.

- **spec-first** (today's default) — *plan, then build.* Front-load the
  speccing: ACs and architecture decided up front, then the autonomous middle
  builds to them.
- **prototype-first** — *build, then spec.* Front-load the building: iterate a
  rough artifact fast until the concept is proven, then **derive** the ACs, spec
  and architecture from the converged artifact.

Prototype-first is the sharp edge of "don't overspec ahead": it defers *all*
speccing until a running thing has answered "what should this even be." The
takeaway from using it is **speed** — no feature list, no stories, just the
concept and iterations.

## Stage mapping — the same checkpoints, entered differently

| checkpoint | spec-first | prototype-first |
|---|---|---|
| **entry** (discuss / feature-init) | create a Ready feature | **offer the prototype path** |
| **prototype** (iteration 0) | — | iterate fast, N rounds, concept-only, until it converges |
| **CP2 ACs** | human writes them up front | **reverse-engineer** them from the prototype (`discover-acs` reverse-engineer mode — the same one onboarding uses) |
| **CP3 spec** | formalize ACs → Gherkin | derive specs from the prototype + ACs; the prototype is the `gauntlet:` bar |
| **CP4 plan** | architecture decided up front (human) | **retrofit** architecture from the prototype's shape |
| **CP5 implement** | build to the spec | **disposition-dependent** (below) |
| **CP6 refine** | identical | identical |
| **CP7 verify / CP8 harden** | identical | identical |

Nothing is thrown away — every stage has a place in both paths. Prototype-first
just runs CP2–CP4 as *derive-from-artifact* instead of *decide-up-front*, and
the human's judgment lands on the **converged prototype** (a running thing they
can see) instead of on prose.

## The convert-to-spec pivot

When a prototype converges, *promote* pivots it into the pipeline: create the
feature, copy the prototype in as the tracked reference, reverse-engineer the
ACs, retrofit the plan. What happens to the rough prototype **code** is
**size-dialed** (reuses `size` / `references/gate-profile.md`):

| `size` | disposition | CP5 implement |
|---|---|---|
| **S / M** (low-risk) | **harden in place** | the prototype code *is* the starting implementation; refine + verify + harden clean it (Uncle Bob's bet: strong gates beat the cruft) |
| **L / XL** (or risky) | **rebuild against the bar** | implement fresh against the derived spec; the prototype is the `gauntlet:` bar the result must match; its code is thrown away |

Recorded on `feature.md` at convert time as `prototype_disposition: in-place |
rebuild` (defaulted from size, overridable). CP5 reads it.

## Deliberately not built — micro-prototyping within a feature

`prototype` is a **feature-level entry path only.** Prototyping individual pieces
*inside* a feature's implementation is out of scope — a risky sub-part spike
during CP5 is just normal implementation exploration, not a formal stage. The
recursion buys little and muddies the model.

## Which path?

Not a hard rule — the human chooses at discuss/feature-init. Prototype-first
suits fuzzy, UX-heavy, or "I'll know it when I see it" work; spec-first suits
well-understood work where the shape is clear before building. Both honor "human
at the ends" — the human still owns the ACs/architecture decision and the
verification; prototype-first just moves *when* the architecture decision is
made (after the artifact exists) without removing it.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/prototype/SKILL.md` — the prototype-first entry + convert pivot
- `${CLAUDE_PLUGIN_ROOT}/references/gauntlet.md` — the prototype as reference bar
- `${CLAUDE_PLUGIN_ROOT}/references/gate-profile.md` — the `size` dial the disposition reuses
- `${CLAUDE_PLUGIN_ROOT}/skills/discover-acs/SKILL.md` — reverse-engineer mode = convert-to-ACs
- [Direction — Human at the Ends & the Control Surface](https://app.notion.com/p/3c35ecdee0e2814f9f4bcdd21c7f206d)
