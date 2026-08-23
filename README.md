# Disciplined Agentic Engineering (DAE)

*A methodology kit for engineering-led AI development — spec-driven, test-driven, charter-bound. ATDD + mutation testing + deterministic guardrails.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Reference host: Claude Code](https://img.shields.io/badge/reference%20host-Claude%20Code-blueviolet)](https://github.com/swingerman/engineer)

**AI agents do the typing. Engineers stay in charge of architecture, behavior contracts, and verification.** DAE puts the discipline in *deterministic tools the agent has to satisfy* — not in prompt rules that erode over long runs.

The methodology is host-independent. It ships today as three plugins for **Claude Code**, the reference host — see [Host independence](#host-independence).

> ℹ️ **Repo renamed** to `swingerman/engineer` (formerly `swingerman/atdd`, then `swingerman/disciplined-agentic-engineering`). Old URLs still redirect; update remotes only if you want to: `git remote set-url origin https://github.com/swingerman/engineer.git`. The marketplace is still named `disciplined-agentic-engineering` — install refs (`@disciplined-agentic-engineering`) are unchanged.

---

## Contents

| | |
|---|---|
| **[Quick start](#quick-start)** · [Install](#install) · [Your first feature](#your-first-feature) | Get running |
| **[How it works](#how-it-works)** · [The pipeline](#the-pipeline) · [Guardrails](#the-guardrails) · [Autonomy](#tunable-autonomy) | The methodology |
| **[The three plugins](#the-three-plugins)** · [`engineer`](#engineer--the-methodology-kit) · [`atdd`](#atdd--acceptance-test-driven-development) · [`crap-analyzer`](#crap-analyzer--change-risk) | What's in the box |
| **[Host independence](#host-independence)** | Porting to another runtime |
| **[Why not vibe coding](#why-not-vibe-coding)** · [Who it's for](#who-its-for) · [Background](#background--influences) | The argument |
| **[Repo layout](#repo-layout)** · [Contributing](#contributing) | Reference |

---

## Quick start

### Install

On Claude Code:

```shell
/plugin marketplace add swingerman/engineer

/plugin install engineer@disciplined-agentic-engineering      # the DAE methodology kit
/plugin install atdd@disciplined-agentic-engineering          # ATDD + differential mutation testing
/plugin install crap-analyzer@disciplined-agentic-engineering # change-risk analysis
```

Or run from a clone:

```bash
git clone https://github.com/swingerman/engineer.git
claude --plugin-dir ./engineer
```

### Your first feature

```shell
/engineer.onboard        # once per project — charter, manifest, tracker
/engineer.next           # every session — "what should I pick up?"
/engineer.discuss        # an idea → drop, park, or promote to a feature
```

From there the pipeline tells you the next command at every step. Each checkpoint
ends with a handoff naming what comes next, and `/engineer.next` reconstructs
that at any time.

---

## How it works

DAE operates on **features** — numbered folders that accumulate a stack of
progressively-sharper specs, Speckit-style:

```
feature.md  →  acs.md   →  spec.md   →  plan.md
intent         behavior     Gherkin      architecture
               (domain      (executable)
                language)
```

Each layer is reviewed and approved before the next is written, and constrains
the ones below it. The folder also holds `handoffs/` (the audit trail) and
`.build/` (generated IR and pipelines).

### The pipeline

Eight checkpoints, each gated on the previous one's handoff:

```
0 Onboard → 1.5 Ready → 2 ACs → 3 Spec → 4 Plan → 5 Implement → 6 Refine → 7 Verify → 8 Harden
```

| # | Stage | Command | What happens |
|---|---|---|---|
| **0** | Onboard | `/engineer.onboard` | Once per project. Human signs off the **charter** (architecture, conventions, quality + autonomy stance); manifest and `features/` layout produced. |
| **1.5** | Ready | `/engineer.feature-init` | `feature.md` records outcome, scope, owner, autonomy level, branch. The contract for *what we're building*. |
| **2** | ACs | `/engineer.discover-acs` | Four-pass interview — happy path, edges, errors & security, cross-cutting. Output `acs.md` in domain language. Reviewed by an adviser + devil's-advocate panel. |
| **3** | Spec | `/engineer.atdd` → `atdd:atdd` | ACs become standard Gherkin in `spec.md`; a project-specific test pipeline is generated. Leakage caught by `spec-guardian`. |
| **4** | Plan | `/engineer.plan` | Architecture plan + structured **Charter Check**. Human confirms the architecture before the rest drafts. Panel-reviewed. |
| **5** | Implement | `/atdd:atdd-team` | Fresh-per-phase agent team implements against the specs. **Two test streams** (acceptance + unit) must go green together. |
| **6** | Refine | `/engineer.refine` | Parallel review across Reuse / Quality / Efficiency, fed deterministic duplicate findings, filtered through the charter. |
| **7** | Verify | `/engineer.arch-check` + `crap-analyzer` | Architecture fitness (layering, cycles, forbidden patterns, naming, size) + change-risk on the diff. **A different agent than the implementer.** |
| **8** | Harden *(optional)* | `/atdd:atdd-mutate` | **Differential mutation testing** proves the unit tests actually catch bugs. |

Cross-cutting, any time: `clarify` · `consistency-check` · `feature-edit` ·
`progress-log` · `reorient` · `session-summary` · `next`.

### The guardrails

**Every checkpoint is gated by tools, not by prompt rules.** An agent can talk
itself out of an instruction; it cannot talk itself out of a non-zero exit code.
At each checkpoint's Step 0:

| Gate | Script | Enforces |
|---|---|---|
| **Entry** | `dae_handoff.py` | The prior checkpoint's handoff exists, `status: complete`, every exit criterion met |
| **Branch** | `dae_branch.py` | You're on the feature's branch (`git.manual: true` opts out) |
| **Ontology** | `dae_ontology.py` | Artifact-graph constraints — enumerations, AC↔scenario coverage, verifier ≠ implementer |
| **Breadcrumb** | `dae_progress.py` | Passive "you are here" across the pipeline + roadmap |

All 21 scripts are **stdlib-only Python 3**, each with a `test_*.py` sibling —
483 tests. No dependencies is a deliberate portability constraint, not an
aesthetic one.

<details>
<summary><b>The full guardrail set</b> (21 scripts)</summary>

| Script | Purpose |
|---|---|
| `dae_resolve.py` | Methodology-root + manifest resolver; central schema validation |
| `dae_handoff.py` | Handoff-as-gate; project-wide status survey |
| `dae_branch.py` | Branch hygiene at every checkpoint entry |
| `dae_progress.py` | Pipeline breadcrumb + roadmap position |
| `dae_ontology.py` | Artifact-graph constraint checks (see `references/ontology.md`) |
| `dae_arch.py` | Architecture fitness — layering, cycles (Tarjan's SCC), naming, file size |
| `dae_impact.py` | Test Impact Analysis — run only the scenarios a change affects |
| `dae_mutmap.py` | Differential mutation — re-mutate only what changed |
| `dae_dup.py` | Duplicate-code detection (`jscpd` by default, configurable), fed into Refine's Reuse lens |
| `dae_gherkin.py` | Portable Gherkin → IR parser (+ `_convert`, `_mutate` siblings) |
| `dae_reconcile.py` | Reconciles feature state against git/PR reality |
| `dae_release.py` | Version bump + cache sync for the plugins themselves |
| `dae_commit.py` | Commit with bounded retry and safe stale-lock removal |
| `dae_roadmap.py` · `dae_tracker_local.py` | Roadmap + tracker drivers |
| `dae_delegable.py` | Cloud-vs-local dispatch routing |
| `dae_infra.py` | Declared infrastructure probe / start / teardown |
| `dae_introvert.py` | Flags tests that pass without asserting on output |
| `dae_fix.py` | Bug-fix lifecycle + gap analysis |

</details>

### Handoffs

Every agentic task ends with a structured handoff — frontmatter plus body —
carrying its checkpoint, artifacts, exit-criteria assertions, panel findings, and
`recommended_next`. Two jobs:

- **You** know when to re-engage after walking away.
- **The next checkpoint's entry gate** uses it to decide whether it may proceed.

A checkpoint is not done until its handoff says so and the tools agree.

### Tunable autonomy

Every feature carries an explicit **autonomy level** — how much the agent
decides alone versus asking for sign-off. Set at `feature-init`, recorded in
`feature.md`, constrained project-wide by `.engineer/manifest.yml`'s `autonomy.allowed_levels`,
tightened for sensitive paths (security, billing) via path overrides.

| Level | Behavior |
|---|---|
| `low` | Confirm before dispatching the next checkpoint. Review-everything mode. |
| `medium` | Auto-dispatch, announced in one line. |
| `high` | Auto-dispatch silently; report outcomes. "Agent, go cook." |

Some gates ignore the dial: `plan` always asks the human to confirm the
architecture, and **outward-facing writes** (pushing to `main`, opening or
merging PRs, self-modifying agent config, writing to live systems) always
require explicit authorization — even at `high`.

<details>
<summary><b>Worked example</b> — feature 015, idea to merge</summary>

```text
# Session 1 — idea to spec
$ /engineer.discuss
  [brainstorm: "add image upload to user profile"] → promote (autonomy: medium)
  Created features/015-image-upload/{feature.md, handoffs/, .build/} + branch

$ /engineer.discover-acs
  [four-pass interview] → acs.md, 8 ACs in domain language
  [adviser + advocate panel] → 2 findings, 1 accepted
  Handoff → human review

$ /engineer.atdd
  → spec.md (4 scenarios, standard Gherkin) + .build/spec.json + test pipeline

# Session 2 — plan and build
$ /engineer.plan
  [agent proposes architecture; human confirms; rest drafts]
  → plan.md (Charter Check: 0 deviations)

$ /atdd:atdd-team
  [fresh agent per phase] → both test streams green
  [refine → arch-check → crap-analyzer → differential mutation]

# Session 3 — wrap
$ /engineer.session-summary
  → session-log.md, next-tasks: open the PR
```

At every step the entry gate verifies the prior handoff, the branch check
verifies you're on `image-upload`, and the breadcrumb shows where you are in the
pipeline and on the roadmap.

</details>

---

## The three plugins

| Plugin | Purpose | Version |
|---|---|---|
| **[`engineer`](engineer/)** | The DAE methodology kit — 18 skills, 21 guardrail scripts, the checkpoint pipeline | 0.21.0 |
| **[`atdd`](./)** | ATDD workflow, team orchestration, differential mutation testing, portable Gherkin pipeline | 0.8.2 |
| **[`crap-analyzer`](crap-analyzer/)** | Change Risk Anti-Pattern analysis on changed code | 0.1.1 |

### `engineer` — the methodology kit

<details>
<summary><b>All 18 skills</b></summary>

| Skill | Role |
|---|---|
| `onboard` | Project bootstrap — charter, manifest, tracker (CP0) |
| `discuss` | Upstream funnel — brainstorm; drop / park / promote |
| `feature-init` | Produces `feature.md`, folder, branch, tracker entry (CP1.5) |
| `prime-context` | Orient on a Ready feature before AC discovery |
| `discover-acs` | AC discovery interview → `acs.md` (CP2) |
| `atdd` | CP3 entry point — bridges into `atdd:atdd` |
| `plan` | Architecture plan + Charter Check → `plan.md` (CP4) |
| `refine` | Parallel reuse / quality / efficiency review (CP6) |
| `arch-check` | Architecture fitness — layering, cycles, naming, size (CP7) |
| `fix` | Bug lifecycle, with a "why didn't we catch it?" gap analysis |
| `reorient` | Mid-task re-anchoring after compaction or a long run |
| `clarify` | Single-artifact ambiguity resolution |
| `consistency-check` | Cross-artifact validation, read-only |
| `feature-edit` | Intent-driven edits with downstream cascade |
| `progress-log` | Handoffs → `progress.md` + tracker sync |
| `session-summary` | Per-session `session-log.md` entry |
| `post-merge` | Branch cleanup + state reconcile after a merge |
| `next` | Session-start survey — what to pick up now |

</details>

Deeper detail lives in the repo, not here: `engineer/skills/*/SKILL.md` for each
skill's workflow and exit contract, and `engineer/references/` for the shared
contracts — handoff schema, progress indicators, review panel, model classes,
host capabilities, ontology, parallelism, and more.

### `atdd` — Acceptance Test Driven Development

> "Specs will be co-authored by the humans and the AI, but with final approval,
> ferociously defended, by the humans." — Robert C. Martin

Packages [Robert C. Martin's](https://en.wikipedia.org/wiki/Robert_C._Martin)
approach to applying ATDD against agentic AI coding, as developed in
[empire-2025](https://github.com/unclebob/empire-2025).

**Two problems it solves.** Without acceptance tests anchoring behavior, an agent
"willy-nilly plops code around" and writes unit tests that pass without verifying
anything worthwhile. And left alone, agents fill Given/When/Then with class
names, endpoints, and table names instead of domain language.

```shell
/atdd:atdd Add user authentication with email and password
/atdd:spec-check     # audit specs for implementation leakage
/atdd:mutate         # verify the tests actually catch bugs
/atdd:kill-mutants   # write tests targeting survivors
```

**The Golden Rule:** specs describe *what* the system does, never *how*.

| ❌ Implementation leakage | ✅ Domain language |
|---|---|
| `Given the UserService has an empty userRepository` | `Given there are no registered users` |
| `When a POST is sent to /api/users with JSON body` | `When a user registers with email "bob@example.com"` |
| `Then the database contains 1 row in users` | `Then there is 1 registered user` |

<details>
<summary><b>The loop, and what a spec looks like</b></summary>

```
1. Write Given/When/Then specs — natural language, domain only
2. Generate the test pipeline (parser → IR → test generator),
   which has deep knowledge of your codebase internals
3. Run acceptance tests → they FAIL (red)
4. Implement with TDD until BOTH streams pass
5. Review specs for implementation leakage
6. Mutation testing → verify the tests actually catch bugs
7. Next feature, back to 1
```

Specs are **standard Gherkin** in `spec.md`:

```gherkin
Feature: User registration

Scenario: User can register with email and password
  Given no registered users
  When a user registers with email "bob@example.com" and password "secret123"
  Then there is 1 registered user
  And the user "bob@example.com" can log in
```

Migrating from the legacy `;=== .txt` format? Run
`dae_gherkin_convert.py specs/feature.txt features/NNN-slug/spec.md` from the
`engineer` plugin's `scripts/`. The `.txt` format is deprecated.

</details>

**Three validation layers**, each answering a different question:

| Layer | Asks |
|---|---|
| Acceptance tests | **WHAT** — does the external behavior match the contract? |
| Unit tests | **HOW** — is the internal structure right? |
| Mutation testing | **REAL?** — do those tests actually catch bugs? |

**Differential mutation testing** keeps layer 3 affordable: `dae_mutmap.py`
maintains a committed manifest keyed by function, and re-mutates one only when
its code, its covering tests, or the operator set changed. The hash triple makes
the cache safe to share across CI, fresh clones, and every developer.

<details>
<summary><b>atdd plugin components</b></summary>

| Component | Name | Purpose |
|---|---|---|
| Skill | `atdd` | 7-step workflow: specs → pipeline → red/green → iterate |
| Skill | `atdd-team` | Fresh-per-phase agent team across six phases |
| Skill | `atdd-mutate` | Mutation testing with differential re-runs |
| Agent | `spec-guardian` | Catches implementation leakage in Given/When/Then |
| Agent | `pipeline-builder` | Generates a bespoke parser → IR → test generator |
| Hook | PreToolUse | Warns when writing code without acceptance specs |
| Hook | Stop | Reminds you to verify both test streams |

The generated pipeline is **not** Cucumber — "a strange hybrid of Cucumber and
the test fixtures" (Uncle Bob). The parser/generator has deep knowledge of your
system's internals and emits complete, runnable tests. No manual fixture code.

</details>

### `crap-analyzer` — change risk

Change Risk Anti-Pattern analysis over changed code: complexity × lack of
coverage, scoped to a diff. Multi-language. Part of Checkpoint 7 alongside
`arch-check`.

---

## Host independence

DAE is a **methodology**, not a set of host features wearing a methodology's
name. The pipeline, the checkpoint contract, the artifact schemas, and the
`dae_*.py` guardrails are host-independent by construction — stdlib-only Python 3
with no dependencies, precisely so that stays true.

What *is* host-specific is the mechanism each capability is reached through. The
skills name Claude Code's mechanisms directly ("dispatch via the Agent tool")
because that's the host they run on today — but those names are **bindings, not
the contract**. `engineer/references/host-capabilities.md` holds the seam:

| | Capabilities |
|---|---|
| **Required** | dispatch a fresh agent · filesystem · script execution |
| **Optional** | progress surface · structured ask · orchestration · isolation · remote execution · peer messaging · tool channels · rendered views |

Every optional capability has a specified degradation, so a host that lacks one
loses a convenience, never the methodology. **Porting is editing that table's
binding column**, plus the plugin-root path prefix and the host hook examples.

The same discipline applies to models: `engineer/references/model-classes.md`
names capability *classes* — `economy` / `inherit` / `frontier` — rather than
product names, which get deprecated, and resolves them against the host's live
model list at dispatch time.

Optional capabilities are used when present and never depended on. A rendered
board is a better answer to "where are we" than four lines of breadcrumb, so DAE
offers one where the host can publish views — and always emits the terminal text
regardless.

---

## Why not vibe coding

**Vibe coding** is prompting loosely — *"build me a thing that does X"* —
accepting what comes back, running it, patching when something feels off. No
charter, no behavior contract, no verification gates. Fast at first, brittle
over time: the codebase drifts, tests pass without proving anything, regressions
surface when users find them.

| | Vibe coding | DAE |
|---|---|---|
| **Architecture** | emerges from prompts | engineered upfront; `CHARTER.md` enforced by `arch-check` |
| **Behavior contract** | "whatever the agent built" | ACs + Gherkin, human-approved, leakage-checked |
| **Verification** | run it and see | two test streams + change-risk + mutation testing |
| **Gates** | none | handoff-as-gate, branch hygiene, ontology, exit criteria |
| **Refactoring safety** | tests may not catch regressions | mutation-tested suite = *semantic firewall* |
| **Autonomy** | implicit, drifts | explicit per feature, manifest-constrained |
| **Discipline lives in** | a prompt (and erodes) | tools the agent can't argue with |
| **Pace** | fast initially | steady, sustainable |

Shipping something quick and disposable? Vibe coding is fine. Building something
you intend to maintain — with agents helping without eroding what they touch?
That's what this is for.

**The headline outcome is semantic stability.** ATDD plus mutation testing form a
*semantic firewall*: code can be refactored, extended, or rewritten by agents
without the system's intended behavior drifting.

### Who it's for

**Software engineers.** DAE assumes you can read a `plan.md` and judge whether
the architecture is sound; read a Gherkin spec and tell whether it captures
intent; know when a charter rule should be enforced versus amended.

**Not for non-programmers.** "Build an app without code" tools target a different
audience and a different problem. The decisions DAE puts in front of you —
architecture, behavior contracts, charter rules, verification thresholds,
autonomy levels — are engineering decisions that need engineering judgment.

### Background & influences

Programming has always climbed the abstraction ladder: front-panel switches →
punch cards → assembly → high-level languages → managed runtimes → and now,
with capable LLMs, **specification and behavior description as the next rung**.
At every step the rung below fades from daily concern. Nobody hand-writes
opcodes; nobody audits the assembly a compiler emits.

**What never shifts is engineering discipline.** Compiler output earned trust
because the compiler was rigorous *and the inputs were checked*. AI-generated
code earns it the same way: rigorous input artifacts (charter, ACs, specs,
plans) and checked output (two test streams, mutation testing, architecture
fitness, change risk, duplicate and cycle detection). Change the artifact you
author but stop checking the output, and you don't get speed — you get a faster
path to a brittle system.

DAE synthesizes four sources:

| Source | What DAE takes from it |
|---|---|
| **ATDD** (XP / FIT / Fitnesse lineage — Kent Beck, Ward Cunningham, others) | Acceptance tests as a behavior contract. Uncle Bob's [empire-2025](https://github.com/unclebob/empire-2025) showed its particular power as a constraint on *agentic* development — two test streams the agent can't talk past, plus mutation testing as the test-quality firewall. |
| **[Speckit](https://github.com/github/spec-kit)** | Specification is **iterative and layered**, not a one-shot document. Each feature evolves through progressively-sharper specs, each approved before the next. |
| **[Acceptance Pipeline Specification](https://github.com/unclebob/Acceptance-Pipeline-Specification)** (Uncle Bob, 2026) | Portable pipeline: Gherkin → JSON IR → generated tests → runner, with mutation as an IR-level sidecar. |
| **The host's stock `/simplify`** | The three-lens parallel review pattern (Reuse / Quality / Efficiency). DAE's `refine` adds charter validation of every proposal and graceful breaking-change classification. |

Two further debts to Uncle Bob's public writing on ATDD, SDD, and AI-assisted
development: the **swarm-failure observations** that drove DAE's
deterministic-guardrail philosophy, and the **differential-mutation post** that
shaped `dae_mutmap.py`.

DAE's own additions: the Ready contract, autonomy levels, verification
independence, the handoff / exit-criteria contract, the artifact ontology, the
review panel, and the deterministic `dae_*.py` guardrails.

This marketplace contains no code from empire-2025 or other upstream projects —
it adapts the methodology.

---

## Repo layout

```
.
├── .claude-plugin/          # marketplace + atdd plugin manifests
├── agents/ commands/        # atdd plugin agents and commands
├── hooks/ references/       # atdd plugin hooks and references
├── skills/                  # atdd plugin skills (atdd, atdd-team, atdd-mutate)
│
├── engineer/                # the DAE methodology kit
│   ├── references/          # shared contracts — handoff, ontology, panel,
│   │                        #   model classes, host capabilities, parallelism
│   ├── scripts/             # dae_*.py guardrails + their unit tests
│   ├── skills/              # the 18 engineer skills
│   └── examples/            # optional host hook configs
│
└── crap-analyzer/           # change-risk analysis plugin
```

## Contributing

Issues and PRs welcome on
[GitHub](https://github.com/swingerman/engineer).

## License

[MIT](LICENSE)
