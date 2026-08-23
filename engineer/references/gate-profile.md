# Gate profile — human at the ends, agents in the middle

Where the human's **judgment** is required across a feature's pipeline, and how
that depth is **dialed by feature size**. The complaint this fixes: *"I'm asked
to decide things in the middle when I only need to decide at the start (specs +
architecture) and at verification."*

The direction: [Direction — Human at the Ends & the Control Surface](https://app.notion.com/p/3c35ecdee0e2814f9f4bcdd21c7f206d).

## Two gates, autonomous middle

A feature has **two** human decision gates, not one-per-checkpoint:

| Gate | Where | What the human owns |
|---|---|---|
| **Front** | after CP4 (plan) | ACs + spec + architecture, reviewed **together, once** |
| — middle — | CP5–7 (build / refine / harden) | **nothing** — deterministic gates + the gauntlet loop; the human *watches*, does not approve round-to-round |
| **Back** | verify (CP7/CP8) | did it actually work |

The middle is already autonomous at `medium`/`high` autonomy (see
`handoff-dispatch.md`). This reference adds the **front-bundling**: today CP2
(AC approval) and CP4 (architecture confirmation) are **two** separate human
stops with CP3 between them. Under a bundled profile the agent drafts the whole
front — ACs → specs → architecture → plan — **without stopping**, then presents
`acs.md` + `spec.md` + `plan.md` as **one** approval before CP5.

**Architecture stays a human decision** — bundling changes *when* it's approved
(with the rest, once), never *who* decides it.

## The profile

Two dials, carried on `feature.md` as `gate_profile: { front, verify }`:

- **`front`** — `auto` (no front gate; agent runs CP2→CP4 and dispatches CP5) ·
  `bundled` (one human approval of ACs+spec+plan before CP5).
- **`verify`** — `light` · `standard` · `heavy` · `auto`. Sets how hard the
  human validates at the back gate; feeds `validation_method` and `plan`'s Test
  strategy depth. It never lowers the objective gates (acceptance + CRAP +
  mutation always run) — it dials the *human's* attention. `auto` is the top
  notch: **no human back gate — merge when the deterministic merge-readiness bar
  is green, else fall back to human.** See "verify: auto" below; it is never a
  size default.

## Size sets the default

`size` (S/M/L/XL, from `feature-init`) picks the default profile — small
features earn trust cheaply and want eyes on the result; large features earn
their upfront spec and lean on the automated gates:

| `size` | `front` | `verify` | reading |
|---|---|---|---|
| **S** | `auto` | `heavy` | barely spec it, but look hard at the result |
| **M** | `bundled` | `standard` | one front approval, normal verify |
| **L** | `bundled` | `standard` | real front spec+arch, normal verify |
| **XL** | `bundled` | `light` | invest upfront; trust the gauntlet + tests at the end |

Defaults only — a feature may carry an explicit `gate_profile:` that overrides
the size default (e.g. a small but risky payment change → `front: bundled`).

## Composition with `autonomy_level` — the precedence rule

Two axes serving two masters:

- **`autonomy_level`** = *mechanical consent*, **capped by the charter** (a
  payment/auth path pins it `low`). Whether to ask before spawning the next
  agent. See `handoff-dispatch.md`.
- **`gate_profile`** = *decision depth*, dialed by **size/effort**. Which
  judgment stops the human owns.

They meet at one place, and **the safety axis wins**:

> **`autonomy_level: low` suppresses `gate_profile.front` — fall back to
> per-checkpoint decision gates** (review ACs at CP2, architecture at CP4,
> confirm each dispatch). `low` means "I'm reviewing everything anyway," so the
> front dial is moot by design. `front: auto`/`bundled` apply **only at
> `medium`/`high`**.

This turns the collision into the correct behavior: a *small* feature that
touches a charter-flagged path is size-small (→ `front: auto`) yet autonomy-
capped to `low` → it gets **full per-checkpoint review**, not `auto`. Effort
never overrides safety.

The `verify` dial is unaffected by autonomy — it is back-gate depth, not
dispatch. But **`verify: auto` still yields to `low`**: a `low` feature is never
auto-merged (see below). And neither dial ever bypasses the **external-write
gate** (`handoff-dispatch.md`): outward/self-modifying writes always ask, except
the one narrow `verify: auto` merge carve-out defined next.

## `verify: auto` — auto-merge when the bar is green

The deterministic extension of the back gate: exactly what the gauntlet did at
CP5 (a bar-with-a-critic replacing a human-with-an-opinion), now at the merge. A
feature carrying `verify: auto` may **auto-merge its PR** — the one carve-out to
the "PR merge is always human" rule — **iff** `scripts/dae_mergeready.py` reports
`ready: true`. It aggregates the existing signals (all `exit_criteria` met
through the final gate, `dae_ontology` clean, `dae_arch` clean, the gauntlet
cleared if a bar was declared, CI green) and is **fail-closed**: any signal it
cannot affirmatively confirm is a blocker → human.

**Guardrails — these force human even on an all-green bar:**

- **Opt-in, default `human`.** `verify: auto` is a deliberate per-project trust
  decision; it is **never** a size default (the size table tops out at `light`).
- **`autonomy_level: low`** (incl. charter-capped) → human. Safety wins here too.
- A **qualitative surface with no cleared gauntlet bar** → human. You cannot
  auto-merge "does it feel right" without a bar.
- A **charter-flagged / high-blast-radius path** (payments, auth, data
  migration, merge-triggers-prod-deploy) → human.
- A **non-default `validation_method`** (canary, manual smoke, timed soak) is
  inherently human/time-based → human.
- Optional **trust-ramp**: the first *K* merges on a project stay human before
  `auto` engages (Bob's spot-checks).

When it does auto-merge, it posts the readiness bar as the PR comment for the
audit trail, and the human can always revert after the fact. GitHub branch
protection requiring a review is a fine belt-and-suspenders backstop.

## Backward compatibility

**A feature with no `gate_profile:` keeps today's behavior** — CP2 stops for AC
approval and CP4 iterates architecture with the human, per-checkpoint. The
profile is opt-in via `size` (new features get it from `feature-init`) or an
explicit field; absence is not `auto`, it is "unchanged".

## Who reads it

- `feature-init` — derives the default from `size`, writes `gate_profile:`.
- `discover-acs` (CP2) — under `bundled`/`auto` **at `medium`/`high`**, drafts
  ACs and continues without a standalone approval stop; at `low`, per-checkpoint.
- `atdd` (CP3) — already has no human gate; unchanged.
- `plan` (CP4) — under `bundled` **at `medium`/`high`**, drafts the full plan
  without the mid-way architecture-confirm stop, then presents the **front
  bundle** (acs+spec+plan) for one approval; under `auto`, dispatches CP5
  directly; at `low`, per-checkpoint. Test strategy depth follows `verify`.
- the merge point (post-CP7 verification) — the back gate's human depth follows
  `verify`; under `verify: auto` it consults `dae_mergeready.py` and may
  auto-merge on a green bar (guardrails above), else hands to the human.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md` — autonomy + dispatch (the safety dial) + the `verify: auto` merge carve-out
- `${CLAUDE_PLUGIN_ROOT}/references/gauntlet.md` — what makes the autonomous middle safe (the bar)
- `${CLAUDE_PLUGIN_ROOT}/references/review-panel.md` — agent-vs-agent gates at CP2/CP4 (not human gates)
- `${CLAUDE_PLUGIN_ROOT}/scripts/dae_mergeready.py` — the merge-readiness aggregator behind `verify: auto`
