# Review panel — standing adversarial review at the artifact gates

Two agents review a checkpoint's output before the pipeline builds on it: one
**adviser** looking for what's missing, one **advocate** trying to prove a claim
false. They run concurrently, they don't see each other's work, and their
findings land in the handoff whether accepted or rejected.

This exists because the pattern kept getting rebuilt by hand — four times across
four projects (mmc 083, wipist 018, ei-theme 007 and 008), each time as a fresh
~800-word prompt rediscovering the same lessons. It earns its place: those
manual runs found an AC set fencing the wrong perimeter, a plan whose central
factual claim was false, and an unfalsifiable AC — none of which the authoring
agent had noticed.

## The two roles

| Role | Model class | Posture |
|---|---|---|
| **adviser** | `frontier` | Constructive senior review. What is missing, underspecified, or would bite later. Explicitly *not* the advocate — say so in the brief so the two don't converge. |
| **advocate** | `inherit` | Adversarial. Assume the author was too close to the work and that at least one confident claim is false. Find it. |

Two roles, not five. They already produce non-overlapping findings — the adviser
finds gaps, the advocate finds *false statements*. Add a third lens only when a
run shows the pair converging on the same findings; don't pre-build one.

These are **classes, not product names** — model names get deprecated, classes
do not; resolve them against the Agent tool's live `model` enum at dispatch time
per `${CLAUDE_PLUGIN_ROOT}/references/model-classes.md`. The rationale: the adviser
is the archetypal bounded one-shot (read a listed set, return a verdict), which
is the only shape where `frontier` is economical. The advocate inherits because
it argues against a moving target and may need several tool rounds.

## Where it fires

| Gate | Skill | Position |
|---|---|---|
| **CP2 exit** | `discover-acs` | after `acs.md` is written, **before** the handoff and before `atdd` formalizes anything |
| **CP4 exit** | `plan` | after `plan.md` is written, **before** the CP5 implementer is dispatched |
| **CP7** | verification | on request only — expensive, and CP7 already enforces a fresh-agent independence rule |

CP2 is the cheapest place to catch a wrong AC: everything downstream is derived
from it. CP4 is the last point before code exists.

## Autonomy keying

Same table the rest of DAE uses — the source of truth is
`${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md`:

| `autonomy_level` | behaviour |
|---|---|
| `low` | Offer the panel with both roles as the default; wait for the nod. |
| `medium` | Auto-dispatch; announce in one line ("dispatching adviser + advocate on `acs.md`"). |
| `high` | Auto-dispatch silently; report only the verdicts. |

Skip the panel silently when the artifact is trivial — a single-AC feature, a
plan that adds one function to an existing module. The gate is a review of
*judgment*, and there has to be some.

## The brief

Both roles get the same shape. Fill every slot — a panel agent that has to guess
its read set produces plausible-sounding fiction, which is worse than no review.

```
description: <adviser|advocate> — <artifact> for <feature-slug>
subagent_type: <engineer:panel-adviser | engineer:panel-advocate> (or the project
        override; see host-capabilities.md, "Role agents")
model: <frontier for adviser, inherit for advocate — classes, not product
        names; resolve against the Agent tool's live `model` enum>
prompt:
  <role opener — see below>

  ## Project
  <repo root, stack in two sentences, how to run things, dev URL / DB access if relevant>
  A methodology called DAE moves features through checkpoints; you are reviewing
  Checkpoint <N> output.

  ## What to review
  <abs path to the artifact under review>

  ## Read these first
  <numbered list of ABSOLUTE paths — the artifact, its upstream artifacts
   (feature.md, acs.md, the prior handoff), CHARTER.md, and the specific
   source files the artifact makes claims about>

  ## Ground yourself
  Verify the artifact's factual claims against the code and the running system.
  Do not review it as prose.

  ## How to report
  <reporting contract — see below>
```

### Role openers

The role agents (`agents/panel-adviser.md`, `agents/panel-advocate.md`) carry
these openers as their system prompt, and they have no edit tools and a turn
cap. When you dispatch them, skip the opener in the brief. Paste it only when
you fall back to a general-purpose agent.

**Adviser:**

> You are a senior technical adviser reviewing <artifact> before it is built on.
> Your job is CONSTRUCTIVE: what is missing, what is underspecified, what a
> careful senior engineer would add or sharpen. A separate agent is running the
> adversarial review — do not duplicate it. Do not merely praise; find real gaps.
> Give judgment, not a summary.

**Advocate:**

> You are a devil's advocate. Attack the work below. Assume the author was too
> close to the code and too pleased with themselves, and that at least one
> confident claim in it is false. Find it. A separate agent is doing the
> constructive review — do not duplicate it. Do not hedge to be polite; if
> something is fine, say nothing about it.

When the artifact was **reverse-engineered from existing code**, add to both:

> CRITICAL CONTEXT: the code was written FIRST and this artifact was
> reverse-engineered from it. Look hard for statements that are unfalsifiable,
> or that merely describe what the code happens to do rather than what it must do.

### The reporting contract — non-negotiable

Every brief ends with this. It is the fix for panel agents going idle with their
findings stranded in a session nobody reads:

> Your final text is the return value, not a message to a human. It is **not**
> visible to the parent session unless you deliver it through the channel named
> here: <`SendMessage` to "<parent-id>"` | your final text (Agent-tool subagent)>.
> Deliver before you finish, even if your findings are brief or partial. If you
> did not actually run the investigation, say so plainly rather than
> reconstructing something plausible — <the ACs / the plan / the code> will be
> edited based on what you say.

## What comes back

Each finding: a one-line claim, the file and line it concerns, the evidence, and
a severity — `error` (the artifact is wrong or unbuildable as written) or
`advisory` (it would be better if).

Record them in the checkpoint's handoff under `panel_findings[]`:

```yaml
panel_findings:
  - role: advocate
    severity: error
    claim: "AC-7 asserts device_sitemap.php emits 5 URLs; it emits 6."
    location: acs.md:118
    accepted: yes
    disposition: "AC-7 corrected to 6 and cross-checked against the fixture."
  - role: adviser
    severity: advisory
    claim: "No AC covers indexability of the new sitemap."
    location: acs.md
    accepted: no
    disposition: "Out of scope for this feature; parked as a roadmap item."
```

**Rejecting a finding is fine — recording it is not optional.** An undocumented
rejection means the next agent re-litigates the same point, which is exactly the
cost the panel exists to avoid.

## Blocking rule

An **unaddressed `error`-severity finding blocks the checkpoint** at autonomy
`medium`/`high` — the handoff carries `human_action_needed: yes` and the next
checkpoint is not dispatched. At `low`, everything is advisory; the human decides.

"Addressed" means `accepted: yes` with the artifact edited, or `accepted: no`
with a disposition. Silence is not addressing it.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/model-classes.md` — the `economy`/`inherit`/`frontier` classes and how to resolve one to an actual model
- `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md` — autonomy source; the subagent brief template
- `${CLAUDE_PLUGIN_ROOT}/references/parallelism.md` — the two roles are a fixed 2-agent fan-out (Tier 2)
- `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md` — where `panel_findings[]` lives
- `${CLAUDE_PLUGIN_ROOT}/references/host-capabilities.md` — findings read like a review queue; render them as a table where the host can
