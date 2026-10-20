---
name: atdd
description: >-
  Use to drive feature work through the Acceptance Test Driven Development
  workflow — Given/When/Then specs before code, a project-specific test
  pipeline, and two parallel test streams (acceptance + unit). Triggers —
  "/atdd", "build a feature", "implement a feature", "add functionality",
  "start development", "write acceptance tests", "write specs", "use ATDD",
  "use TDD with acceptance tests".
---

# Acceptance Test Driven Development

Enforce the ATDD workflow for feature development. This methodology is
adapted from Robert C. Martin's acceptance test approach.

## Core Principle

> "The two different streams of tests cause Claude to think much more
> deeply about the structure of the code."
> — Robert C. Martin

Two test streams constrain development:
- **Acceptance tests** define WHAT the system does (external observables)
- **Unit tests** define HOW the system does it (internal structure)

Both must pass. Neither alone is sufficient.

## Workflow

Follow these steps strictly, in order. Do not skip steps.

Before Step 1, create one TodoWrite todo per step of this workflow (Steps 1–7),
all at once — the full list up front, as a roadmap. Flip each todo to
`in_progress` / `completed` as you go. See
`${CLAUDE_PLUGIN_ROOT}/references/progress-indicator.md`.

### Step 1: Understand the Feature

Before writing anything, understand what is being built:

- Ask clarifying questions about the feature's purpose
- Identify the domain language (what terms do users/stakeholders use?)
- Determine success criteria: what observable behavior proves it works?
- Scope it: "just enough specs for this sprint" — do not design the whole system

### Step 2: Write GWT Acceptance Specs

Write the feature's `spec.md` in **standard Gherkin** (DAE Foundation §7):

```gherkin
Feature: <feature name>

Scenario: <behavior being specified>
  Given <precondition in domain language>
  And <another precondition if needed>
  When <the action the user/system takes>
  Then <observable outcome>
  And <another observable outcome if needed>

Scenario Outline: <a behavior with varying data>
  Given <a step with a <parameter>>
  ...

  Examples:
    | parameter | expected |
    | value     | result   |
```

`spec.md` is markdown — prose and headings around the Gherkin are fine;
the parser ignores non-Gherkin lines.

> **Migrating from the legacy `;=== .txt` format?** Run the converter:
> `dae_gherkin_convert.py specs/feature.txt features/NNN-slug/spec.md`.
> The `.txt` format is deprecated; new specs are Gherkin `spec.md`.

**Format rules:**
- `Scenario:` names one behavior; `Scenario Outline:` + `Examples:` for varying data
- `Given` sets preconditions; `When` the action (one per scenario, ideally); `Then` the observable outcome
- `And` continues the previous keyword
- Use natural domain language, never implementation language

**The spec-leakage rule — CRITICAL:**

Specs must describe **external observables only**. Never reference:
- Class names, function names, method names
- Database tables, columns, queries
- API endpoints, HTTP methods, status codes
- Framework-specific terms (controllers, services, repositories)
- Internal state, variables, data structures
- File paths or module names

```
BAD:  Given the UserService has an empty userRepository
GOOD: Given there are no registered users

BAD:  When a POST request is sent to /api/users
GOOD: When a new user registers with email "bob@example.com"

BAD:  Then the database contains 1 row in the users table
GOOD: Then there is 1 registered user
```

**Present specs to the user for approval before proceeding.**
Specs are co-authored, but the human has final approval — ferociously defended.

### Step 3: Generate the Test Pipeline

The pipeline's front end is portable and shipped — you don't generate it:

1. **Parser** — `dae_gherkin.py` parses `spec.md` → `.build/spec.json`, the
   fixed JSON IR (see the engineer plugin's `references/spec-ir.md`).

Invoke the `pipeline-builder` agent to generate the **project-specific** half:

2. **Generator** — reads `.build/spec.json`, produces executable test files
   for the project's framework (pytest, Jest, JUnit, Go testing, RSpec, etc.)
3. **Step handlers** — bind each step's exact text to system internals.

The generator must have **deep knowledge of the system internals**.
This is NOT Cucumber — it produces complete, runnable tests that call
into the system, not stubs requiring manual fixtures.

`pipeline-builder` also generates a runner so the user can run:
```
# parse spec.md → IR → generate tests → run tests
./run-acceptance-tests.sh
```

### Step 4: Run Acceptance Tests (Red)

Run the generated acceptance tests. They should **fail** — this confirms
the specs describe behavior that doesn't exist yet.

If they pass, either:
- The behavior already exists (specs are redundant — revise or remove)
- The generator is not testing the right thing (fix the pipeline)

### Step 5: Implement with TDD

Now implement the feature using standard TDD:

1. Write a failing unit test for the smallest piece of the feature
2. Write minimal code to make it pass
3. Refactor
4. Repeat until the acceptance tests pass. The loop is capped: at most 2 × the
   acceptance tests failing at the start, and stop early if a few rounds in a
   row turn no test green (`manifest.autonomy.stuck_loop_threshold`, default 3).
   Either stop means surface the still-red tests rather than keep going.

**Faster iteration with impact analysis:** if the project has
`acceptance.impact_analysis: on`, the runner's impact-run mode (`dae_impact.py
select`) runs only the scenarios your change affects — use it for the tight
TDD loop. The **full** acceptance run still gates Step 5's completion: do not
mark the feature done until every scenario passes a full run.

**Both streams must pass:**
- Unit tests verify internal correctness
- Acceptance tests verify external behavior matches specs

### Step 6: Review Specs for Leakage

After implementation, invoke the `spec-guardian` agent to review all
spec files for implementation details that may have crept in during
development.

If leakage is found, clean the specs back to domain language.

### Step 7: Iterate

Return to Step 1 for the next feature. Each iteration adds specs only
for the current feature — never design the whole system upfront.

## Rules

These rules govern how spec files and the pipeline are handled.
They are non-negotiable.

### Spec file discipline
- **Never modify a `spec.md` without explicit user permission.**
  Specs are the user's contract. Always ask before changing them.
- If a step is ambiguous, **report the ambiguity rather than guessing**.
  Let the user clarify.

### Pipeline discipline
- **Never modify generated test files** in `.build/generated/`.
  Only delete and regenerate them by re-running the pipeline from `spec.md`.
- **`.build/` is gitignored** — the IR and generated tests are artifacts.
  The project-specific generator and step handlers ARE committed source.
- Before running the pipeline, **check modification dates**: if `spec.md`
  is newer than `.build/spec.json` or the generated tests, re-parse and
  regenerate before running.
- **Clear state before each test.** Generated tests must reset all
  application state before each scenario execution to ensure isolation.

### Failure handling
- On test failure, **report the source `spec.md` and the failing
  scenario name**. Traceability back to the spec is critical.
- If a scenario cannot be translated into a test, **still generate it as a
  failing test** that documents the desired behavior. Report to the user
  which scenario and why it could not be fully translated.
- Mock non-deterministic behavior (random numbers, timestamps, etc.) in
  generated tests to ensure reproducibility.

### Before pushing
- Before a git push, **ask the user whether acceptance tests should be
  run**. Do not push without confirming both test streams pass.

## Anti-Patterns to Watch For

### "Let me just write the code first"
No. Specs first, always. The spec-before-code hook will warn about this.

### "The specs are too high-level to test"
Then the specs need to be more specific. Break the feature into smaller
observable behaviors. Each spec should describe one concrete scenario.

### "Let me add implementation details so the generator is easier to write"
This is the perverse incentive. Fight it. The generator should be smart
enough to map domain language to system internals. If it can't, improve
the generator — don't pollute the specs.

### "We only need acceptance tests, unit tests are redundant"
No. Two streams constrain development differently. Acceptance tests alone
leave internal structure unchecked. Unit tests alone miss integration.

## File Organization

DAE stores specs and pipeline artifacts per feature folder:

```
project-root/
├── features/
│   └── NNN-slug/
│       ├── spec.md              # acceptance specs (standard Gherkin) — committed
│       └── .build/              # GITIGNORED (regenerated)
│           ├── spec.json        #   — the IR (from dae_gherkin.py)
│           └── generated/       #   — the generated acceptance tests
├── acceptance/                  # project-specific pipeline — committed
│   ├── generator.*              #   — emits tests from the IR
│   └── handlers.*               #   — step handlers bound to system internals
└── run-acceptance-tests.sh      # pipeline runner — committed
```

### What to commit vs. gitignore

**Commit these (source of truth):**
- `features/NNN-slug/spec.md` — the acceptance specs
- `acceptance/generator.*` — the project-specific generator
- `acceptance/handlers.*` — the step handlers
- `run-acceptance-tests.sh` — the pipeline runner script

**Gitignore these (regenerated from `spec.md`):**
- `features/*/.build/` — the IR and generated tests

Add to the project's `.gitignore`:
```
.build/
```

The parser (`dae_gherkin.py`) is portable and shipped with the plugin —
it is not part of the project's committed source.

### Project CLAUDE.md integration

After setting up the pipeline, add an **Acceptance Tests** section to
the project's `CLAUDE.md` (or create one if it doesn't exist). This
ensures Claude Code understands the ATDD setup in every session:

```markdown
## Acceptance Tests

Acceptance specs are `spec.md` files (standard Gherkin) under
`features/NNN-slug/`.

### Pipeline

```
spec.md → dae_gherkin.py → .build/spec.json (IR) → generator → tests
```

1. **Parse:** `dae_gherkin.py` — `spec.md` → `.build/spec.json` (portable, shipped)
2. **Generate:** [generate command] — reads the IR, produces tests in `.build/generated/`
3. **Run:** [test command] — executes the generated tests

Full pipeline: `./run-acceptance-tests.sh`

### Rules

- Never modify a `spec.md` without explicit permission.
- Never modify generated tests — only delete and regenerate via the pipeline.
- `.build/` is gitignored — do not commit the IR or generated tests.
- Before a push, run the full acceptance test pipeline.
- On failure, report the `spec.md` and the failing scenario name.
```

Adapt the commands and paths to match the project's language and
test framework. The pipeline-builder agent generates this CLAUDE.md
section automatically when creating the pipeline.
