# Model classes — which *class* of model runs which part of the pipeline

Every dispatched agent picks a model. The default — inherit the parent's — is
right for the pipeline proper and wrong at both ends of it: mechanical work a
cheaper model does identically, and bounded one-shot judgment calls worth the
top tier.

**This file names classes, never products.** Model names churn — families are
retired, new ones appear above the old ceiling, and a name pinned into a skill
becomes a silent bug the day it is deprecated. Skills refer to `economy`,
`inherit`, `frontier`, and `diverse`; the mapping to whatever exists today is resolved at
dispatch time, in one place: the rule below.

("Class", not "tier" — `parallelism.md` already uses *tier* for the
parallelism substrate (1/2/3). Two axes, two words.)

## The four classes

| Class | Means | Use for |
|---|---|---|
| **`economy`** | the cheapest tier that reliably executes a deterministic rubric | `atdd:spec-guardian`, `atdd:pipeline-builder`, `Explore`/search fan-outs, `consistency-check --project` per-feature fan-out, `progress-log`, `arch-check`, `post-merge`, any step whose real work is running a `dae_*` script and reporting its output |
| **`inherit`** *(default)* | whatever the session is already running | `discover-acs`, `plan`, CP5 implement, `refine`, `fix`, `discuss`, the review **advocate**. The pipeline proper — where judgment lives and the tokens are earned. Do not economize here. |
| **`frontier`** | the highest-capability tier available, whatever it currently is | Bounded one-shot judgment: the review **adviser** at CP2/CP4, a CP7 independent verdict. Only economical when the read set is *listed in the brief* and the agent returns a verdict rather than iterating. |
| **`diverse`** | a model from a **different family** than the one doing the work | A second opinion that doesn't share the worker's blind spots: the review **advocate** at CP2/CP4 and a **second CP7 verifier** — only when `scripts/dae_diverse.py` says so (L/XL or charter-flagged; never XS/S or express). See `review-panel.md`. |

There is deliberately no fourth "cheapest possible" class. The smallest models
carry materially smaller context windows, and DAE agents routinely load
`feature.md` + `acs.md` + `spec.md` + `plan.md` + `CHARTER.md` plus source. A
class that silently truncates the contract is worse than no class.

## Resolving a class to an actual model

**At dispatch time, read the `model` enum on the Agent tool you are about to
call and pick from it.** That enum is supplied by the harness and is current by
construction — it is the only model list in the system that cannot go stale.

- `economy` → the smallest alias in the enum whose context window still fits the
  brief's read set. In practice the mid-tier alias, not the smallest one.
- `inherit` → omit the `model` field entirely. Never name the parent's model:
  the point is to follow it when it changes.
- `frontier` → the alias the enum documents as most capable. When two are
  equally capable, prefer the cheaper.
- `diverse` → first, an alias in the enum documented as a different model
  family from the session's. Else the project's `models.diverse` manifest
  entry: a shell command that takes the brief on stdin and prints the reply
  (any other-family agent CLI the project has). Else fall back to `frontier`
  and record one line in the handoff: `diverse: unavailable — fell back to
  frontier`. A same-family run is still a review; it just isn't a second
  family, and the note keeps anyone from reading it as one.

If the enum offers only one option, every class resolves to it and the
distinction costs nothing. If a class's intent cannot be honoured, dispatch
anyway with the closest available option — a model choice is never worth
blocking a checkpoint over.

### Dated snapshot — a hint, not the contract

As of **2026-07-29** the aliases were `haiku`, `sonnet`, `opus`, `fable`, and
the classes resolved to `sonnet` / *(omit)* / `fable`, and `diverse` had no
enum option (all one family) — it needed `models.diverse` or fell back. Recorded so a reader can
sanity-check the rule against a known-good example. **Do not treat this line as
authoritative** — resolve from the live enum, and if it disagrees with this
snapshot, the enum is right and this line is stale.

## Picking a class

Ask, in order:

1. **Is the charge mechanical?** A fixed rubric, a schema check, codegen from an
   IR, a search-and-report, a script wrapper → `economy`.
2. **Is it a bounded one-shot judgment call?** The agent reads a listed set of
   files exactly once and returns an opinion, with no build/edit/iterate loop
   → `frontier`.
3. **Otherwise** → `inherit`. Multi-turn work, anything that edits files,
   anything whose read set is discovered as it goes.

`diverse` is never picked by this judgment. `dae_diverse.py <feature-dir>`
decides it from `feature.md`, so a small feature can't pay for it and a large
one can't skip it.

Decide this **per dispatch, from the actual charge** — the same way parallelism
is discovered per run. `refine` over a 2-file change is mechanical; `refine`
across 40 files with a charter-conformance argument is not. Never hardcode a
class into a skill either.

## Why the classes are shaped this way

**Real numbers first.** Where the engineer mods load (`host-capabilities.md`,
host hooks), the `mcp__engineer__cost_ledger` tool returns the actual tokens and
minutes per role × class × shape across past sessions. Use those over the
analysis below and the priors in `parallelism.md`; fall back to them only for a
combination the ledger has not seen.

A cost observation from 21 DAE sessions (2026-07-10 → 07-29). The specific
numbers date quickly; the *shape* is what the classes encode:

- **98% of input tokens were cache reads.** Prompt length is not the cost lever.
  The per-model input rate still dominates a long run, because cache reads bill
  as a fraction of it — so *which class carries the long-context loop* is the
  decision that matters.
- The top class took **23% of spend for 4% of the output** — it read a great deal
  and wrote very little. That is the correct shape for a one-shot adviser and
  the wrong shape for anything that loops. **Never put `frontier` in an agentic
  harness.**
- **101 of 157 subagent dispatches inherited the session model**, including
  purely mechanical ones. That is where the count is, and why `economy` exists.

## Interaction with prompt caching

Switching models mid-conversation invalidates the cache — caches are
model-scoped. That is an argument *for* pushing cheap work into a **subagent**
rather than switching the main loop's model: the subagent pays its own cold
write, and the parent's cached prefix survives untouched.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md` — the subagent brief template carries the `model:` class
- `${CLAUDE_PLUGIN_ROOT}/references/parallelism.md` — per-shape class priors in the *Common shapes* table
- `${CLAUDE_PLUGIN_ROOT}/references/review-panel.md` — the one place `frontier` is a standing default, and where `diverse` runs
