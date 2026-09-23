---
name: refinement-advisor
description: Use to decide which refinement and hardening tools are worth running on a set of changes — refine, crap-analyzer, arch-check, introversion scan, mutation testing, TLA+ model checking, Lean proofs — and on which files, with the invariant to check. Triggers — "/engineer.refinement-advisor", "what should we harden", "which checks fit this diff", "is this worth TLA+ / Lean", "should we model-check this", "how do I harden this change". Called by /engineer.harden at CP8; also usable ad hoc on any diff, in or out of the pipeline.
---

# refinement-advisor

Reads a diff and recommends which of the DAE refinement/hardening tools to run,
where, and why. It **advises; it does not run the tools.** The expensive ones
(TLA+, Lean) cost real minutes each, and running every tool on every diff buries
the one finding that matters under noise from checks that never fit the code.

The advice is only as good as its reading of the code: read the changed
functions, not just filenames or the diff stat.

## When to use

- Called by `/engineer.harden` (CP8) to pick that checkpoint's tools.
- Ad hoc: "which checks fit this change?", before a risky merge, or when
  deciding whether a piece of code deserves formal verification.

**Not for:** running the tools (`harden`, or the tools' own skills), or reviewing
code quality itself (`refine`).

## Inputs

- **Scope** — a feature dir (diff = feature branch vs its branch point), a fix
  record, a PR, or an explicit ref range. Default: current branch vs its merge-base
  with the default branch.
- **Stage** (optional) — `refine`, `verify`, `harden`, or `any` (default). Limits
  the recommendations to that stage's tools.
- **Prior results** (optional) — if a CP7 handoff exists, read its
  `crap_results` block (arch-check records crap-analyzer's output there). CRAP
  scores tell you where complex, poorly tested code is. Use them; don't redo
  that analysis.

## The toolbox

| Tool | Stage | Answers | Cost |
|---|---|---|---|
| `/engineer.refine` | CP6 | Is the changed code clean: reuse, clarity, efficiency? | medium |
| `crap-analyzer` | CP7 | Where does high complexity meet low test coverage? | low |
| `/engineer.arch-check` | CP7 | Does it respect the charter's layering and naming? | low |
| introversion scan (`dae_introvert.py`) | CP8 | Can a test pass without asserting anything? | low |
| `atdd:atdd-mutate` | CP8 | Do the tests fail when the code is wrong? | medium |
| `/engineer.tlaplus` | CP8 | Can **some interleaving or sequence of events** break an invariant? | high |
| `/engineer.lean` | CP8 | Does an invariant hold **for every input**, including unbounded ones? | high |

**Every tool in scope gets a verdict, `recommend` or `skip`, with a reason.**
Nothing runs by default. A cheap tool that can't find anything in this diff is
still noise, and an expensive one that fits is worth its cost. Judge each one
against the signals below.

## Signals, per tool

**`/engineer.refine`**: recommend when CP6 hasn't run on the current diff, or
code changed since it did. Skip when refine's handoff already covers these
commits.

**`crap-analyzer` / `arch-check`**: recommend when CP7 hasn't run on the
current diff. Skip when a CP7 handoff covers these commits, and reuse its
numbers instead.

**Introversion scan**: recommend when test files were added or changed. Skip
when no tests changed (there is nothing new to scan).

**Mutation (`atdd:atdd-mutate`)**: recommend when the change adds or alters
branching logic (conditions, loops, error paths, boundaries) **and** tests
exercise it. That's where a weak assertion hides. Skip when:
- the change is config, docs, markup, styling, generated code, or trivial
  accessors
- no tests cover the changed code (mutation just reports "all survived", which
  crap-analyzer already told you; recommend writing tests instead)
- mutation already ran on the same files and they haven't changed since
- the risk is temporal (races, ordering). Mutants don't model interleavings, so
  that is a TLA+ job, not a mutation job.

**`tlaplus`**: recommend when the changed code has temporal or concurrent shape:
- retry and backoff loops, timeouts, circuit breakers, rate limiters
- locks, queues, workers, schedulers, cron-style jobs that can overlap
- async/await, promises, callbacks, events, or streams where order matters
- an explicit state machine or status enum with transitions, such as session
  phase, order status, or a connection lifecycle
- multi-step protocols (handshake, cancel/redeliver, two-phase anything)

Races don't raise complexity metrics, so a low CRAP score says nothing here.
Recommend TLA+ based on the shape of the code, not on the risk score.

**`lean`**: recommend when there is a claim of the form "for all inputs X, P
holds", about pure logic:
- parsers, sanitizers, maskers, encoders (e.g. "the output never contains the
  password")
- money, units, rounding, or date arithmetic
- permission and authorization predicates
- ordering, dedup, and merge functions
- a state machine whose invariant must hold over unbounded counts or data. TLC
  only checks a finite model; Lean proves the general case.

Choose between TLA+ and Lean by the question: if you are asking "what if these
happen in a different order", use TLA+. If you are asking "what if the input is
weird", use Lean. If both apply, recommend both, each scoped to its own
function. Skip both for CRUD, glue, configuration, rendering, or straight-line
code with no invariant worth stating, or when a small table-driven test already
covers the whole input space.

## The invariant is the deliverable

For every TLA+/Lean recommendation, draft the invariant in one plain sentence
("attempt count never exceeds MAX_RETRIES and every path exits"). Both formal
skills say the invariant is the one thing that can't be inferred from the code:
it states what must never happen. The advisor's draft is a starting point for
the human to correct. If you can't state an invariant, don't recommend the tool.

## Output

```
refinement-advisor — <scope>  (<N> files changed, stage: <stage>)

| Tool | Verdict | Target | Why | Invariant / focus |
|---|---|---|---|---|
| tlaplus | recommend | ResidentialProxyHttpClient::get() | bounded retry loop, 4 exit paths | attempt ≤ 3; every path returns or throws |
| atdd:atdd-mutate | recommend | ResidentialProxyHttpClient.php | new retry/error branches, covered by 4 tests | — |
| lean | recommend | ResidentialProxyHttpClient::getMaskedProxyUrl() | regex masker, unbounded input shapes | output never contains the password substring |
| introversion scan | recommend | tests/Unit/Http/* | 2 new test files | — |
| crap-analyzer | skip | — | CP7 already ran on these commits (max CRAP 6) | — |
| refine | skip | — | CP6 handoff covers these commits | — |
```

Sort the `recommend` rows by value (the findings you expect relative to their
cost), highest first. Every `skip` row gives its reason. End with a one-line
bottom line, e.g. "TLA+ on the retry loop is the highest-value check; mutation
is next."

## Who decides: autonomy

Autonomy controls **who makes the call**, never which checks are sound. Use
the effective autonomy from `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md`:
the feature's `autonomy_level`, capped by any `manifest.autonomy.path_overrides`
that match the changed files. For a fix record, which has no `autonomy_level`,
start from `manifest.autonomy.default_level` and apply the same path caps. A
`critical` or `blocks_user: true` fix always counts as `low`.

| Effective autonomy | Advisor behaviour |
|---|---|
| `high` | **Decides alone.** Every `recommend` row is selected and every drafted invariant is final. Show the table, then one line naming what will run and why ("Running TLA+ on get() and mutation on 1 file; skipped 4, reasons above"). Don't ask anything. |
| `medium`, `low` | **Asks.** Offers the recommendations as choices (below). Nothing runs that the human didn't pick. |

`manifest.harden.required: true` removes deselection, not the human. The
recommended rows are mandatory, so Q1 isn't asked; list them as settled. Below
`high` the human still confirms each invariant (Q2) and may add skipped checks
(Q3).

## The choices (below `high`)

A table the human then has to answer in prose is a dead end. Offer the
recommendations as **selectable choices**, so acting on the advice takes one
click. If nothing is recommended and nothing was skipped, say so and don't ask
anything.

Use `AskUserQuestion`:

- **Q1 "Which checks should I run?"** (`multiSelect: true`). Skip Q1 when
  `harden.required: true`. Make one option per `recommend` row, in value order,
  and mark the first `(Recommended)`.
  - Label: `<tool> → <target>` (e.g. `TLA+ → get() retry loop`,
    `Mutation → ResidentialProxyHttpClient.php`).
  - Description: the why, the cost in minutes, and for TLA+/Lean the drafted
    invariant.
  - If there are more than 4 recommendations, fold the cheapest ones into a
    single option (`Introversion + arch-check`) so every expensive check keeps
    its own row.
  - The human can add a skipped tool through "Other" ("also run mutation").
- **Q2 (per recommended TLA+/Lean row) "Is this the right invariant for
  `<target>`?"** Offer:
  - `Use as drafted (Recommended)`
  - `Narrower: <a weaker variant>`
  - `Stronger: <a stricter variant>`

  The built-in "Other" lets the human type their own.
- **Q3 (only when `harden.required: true` and something was skipped) "Add any
  of the skipped checks?"** (`multiSelect: true`). Make one option per `skip`
  row, labelled with its skip reason.

Keep to the tool's 4-question limit. If more questions are needed, prioritise
Q2 for the most expensive formal rows.

The output is the selected tools, each with its target and, for TLA+/Lean, the
final invariant.

**No interactive human** (subagent, headless): at `high`, decide as above.
Below `high`, print the same choices as a numbered list with a copy-pasteable
reply line (`reply: "1,3" or "all"`) and stop.

When called by `harden`, also return the table as YAML (`advisor_picks:`) so
harden can record it in `harden_results.advisor`.

## Handoff

Off-pipeline: `checkpoint: null`. When run standalone on a feature, emit a
short handoff per `${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md` with
`recommended_next` set to the highest-value pick. When called from `harden`,
return the picks inline and write no handoff.

## References

- `/engineer.harden`: the CP8 consumer
- `${CLAUDE_PLUGIN_ROOT}/references/gauntlet.md`: the other quality bar (visual/qualitative); not in this toolbox
- `/engineer.tlaplus`, `/engineer.lean`: the formal-verification skills; each has a "Verifying real code" workflow
