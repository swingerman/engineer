# Coordinator — standing instructions for `/engineer.run`

The coordinator takes one feature from CP2 to CP8. It is the **one
model-decided node** in the feature's graph: it chooses the graph. Everything
after that follows fixed edges. It runs one feature only; running several
features in parallel stays with Decarchy, one coordinator per worktree.

Vocabulary (Chain, Branch, Diamond, Star, Loop, …), the loop rule and the
outside-evidence rule: `${CLAUDE_PLUGIN_ROOT}/references/graph-shapes.md`.
The per-step reflex it applies: `${CLAUDE_PLUGIN_ROOT}/references/parallelism.md`.

## Thin by construction

The coordinator must hold a whole feature without compaction, so it reads only:

- `feature.md` **frontmatter** (`autonomy_level`, `gate_profile`, `size`, `branch`)
- handoff **frontmatter** (`status`, `exit_criteria`, `human_action_needed`,
  `findings_summary`, `recommended_next`, `agent_id`)
- `progress.md`'s CURRENT line
- `run-graph.yml` (its own record)
- the JSON from `dae_*` scripts
- each node's reply (capped at ~1,500 tokens by the reporting contract)

It **never** reads source code, `acs.md`/`spec.md`/`plan.md` bodies, or test
output. When it needs to know something about the code, it dispatches a node and
reads the reply. Every node is a **fresh agent** built from the brief template
below.

## Segments: the human gates split the graph

Workflows take no mid-run input, so no segment may span a human gate. The
boundaries are fixed:

| Segment | Checkpoints | Ends at |
|---|---|---|
| **front** | CP2 → CP4 | **front gate** (one approval of acs + spec + plan) |
| **middle** | CP5 → CP8 | **back gate** (verify + harden: did it actually work), then the merge under the external-write gate |

With per-checkpoint gates (`low`, or no `gate_profile`), the front splits once
more: **CP2** (AC approval) | **CP3 → CP4**. The architecture confirm inside CP4
comes back as a `DECISION` from the plan node, and the coordinator asks the
human and continues the node.

Whether anyone actually waits at a boundary is decided by `gate_profile` and
`autonomy_level`, exactly as in `${CLAUDE_PLUGIN_ROOT}/references/gate-profile.md`.
Under `front: auto` nothing waits at the front boundary; under `verify: auto` a
green `dae_mergeready.py` replaces the back gate. Record the effective front as
`front: bundled | auto | per-checkpoint` in the graph, because `dae_graph.py`
derives the gate positions from it. The external-write gate in
`handoff-dispatch.md` does not change.

## The run

### 0. Resolve and branch at entry

1. Resolve the root and manifest (`dae_resolve.py`). If `<feature>` does not
   resolve to a folder, run `/engineer.feature-init` with it first. Its sizing
   choice point is the funnel.
2. **Express branch.** If `gate_profile.lane: express`, hand the feature to
   `/engineer.express` and stop. No graph, no coordinator overhead.
3. Enforce branch hygiene (`dae_branch.py`). Read
   `dae_handoff.py <feature-dir>` to find the latest complete checkpoint. The
   run starts at the next one, so a half-done feature resumes instead of
   restarting. An existing `run-graph.yml` resumes as well, unless it has drifted
   (step 3).

### 1. Propose the shape, together with the front gate

Build the graph for the remaining checkpoints with the rubric below, write it to
`features/NNN-<slug>/run-graph.yml`, and validate it:

    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dae_graph.py features/NNN-<slug>/run-graph.yml

A non-zero exit is a broken graph: an uncapped loop, a fan-out verified only by
judgment, a segment spanning a gate, or a product name where a model class
belongs. Fix it before showing anything. Never run a graph that fails this
check.

Render the proposal as a **choice point** (`${CLAUDE_PLUGIN_ROOT}/references/choice-points.md`).
For each segment, show the shapes, each node's role, model class and loop cap,
and the estimated tokens and wall-clock. Recommend it, list one cheaper and one
more thorough alternative, and default on silence according to
`autonomy_level`. It is asked **together with the front gate**:

- **`front: bundled`.** Shape the front segment cheaply and show the proposal at
  the start. The full middle-segment proposal goes out with the bundle at the
  front gate, when the plan exists and N is known. That is one human stop for
  both decisions.
- **`front: auto`.** The proposal is the only front stop, at `low`. At
  `medium`/`high` it is reported, not asked.

### 2. The dispatch loop

For each segment, in order:

1. **Pick the substrate** per segment, degrading 3 → 2 → 1
   (`parallelism.md`). A segment is Tier 3 (a Workflow script) only when it is a
   pure fan-out whose nodes need nothing from each other mid-segment. That fits
   CP6's lens Diamond or CP8's formal-check Diamond. Otherwise use Agent
   dispatch: one node at a time for a Chain (Tier 1), several Agent calls in one
   message for a small fan-out (Tier 2). Invoking `/engineer.run` is the opt-in
   for the Workflow tool, and the proposal has already shown its cost.
2. **Ensure infrastructure** once per segment (`dae_infra.py ensure`, per
   `handoff-dispatch.md`), and again only after a failure. **Dispatch each node** with the
   brief template below. Assign the node's
   `agent_id` yourself, `run-<node-id>-<attempt>`, and put it in the brief. IDs
   are distinct per node by construction, so the refiner can never share an id
   with the implementer, nor the verifier with either.
3. **Serve yields.** A coordinated node cannot spawn its own subagents. When it
   reaches a step that dispatches (a review panel, refine lenses, a gauntlet
   critic, formal checks), it **yields**: it returns the briefs and waits. Run
   them as the shape they form (Star, Diamond or Feedback) and continue the node
   with the results via `SendMessage`. A `DECISION` is served the same way:
   hold it for the next gate, or ask now when per-checkpoint gates apply. If the host cannot continue an agent,
   dispatch a fresh node with the partial handoff and the results instead. A
   yielded loop (the gauntlet) runs under the node's declared cap, and you count
   the rounds.
4. **After each node returns**, check the outside evidence before anything else:
   - `dae_handoff.py <feature-dir> --through <cp>`: the handoff exists, is
     complete, every criterion is met, and Principle 7 holds (CP6 ≠ CP5,
     CP7/CP8 ≠ both);
   - for a fan-out node, the `verified_by: tool|human` check named in the graph
     actually ran. A test run counts; another agent's opinion does not.

   Run `dae_ontology.py <feature-dir>` once per segment, before its gate.
   Its Principle 7 check repeats the handoff gate, so running it per node adds
   nothing.
5. **Record the actual result** for each node (node, agent_id, status, rounds,
   tokens and minutes when the host reports them). Write them under `actual:` in
   `run-graph.yml` once per segment, not per node.
6. **Tracker sync** is not the coordinator's job when the engineer mods load:
   their handoff-write hook dispatches it on every handoff write, in the
   background. You can tell the mods are loaded because the
   `mcp__engineer__cost_ledger` tool is listed. If it is not, dispatch an
   `economy` `/engineer.progress-log <slug>` node (Tier 1, fire and forget).
7. At a segment boundary, stop for the gate if there is one (see Segments),
   otherwise go to the next segment.

### 3. Re-shape on drift

Re-derive the remaining graph when what it was built on changes:

- **N grew or shrank.** The plan touches 40 files rather than 4, so CP6 moves
  from Tier 2 to Tier 3. Survivors appear where none were expected.
- **A node failed or returned less** (see Failure handling).
- **A loop stopped** on its cap or on no-progress.

Append a `reshapes:` entry (`at`, `reason`, `change`), re-run `dae_graph.py`, and
report the change in one line. Ask only at `low`. A re-shape never removes a
gate, a verifier or an outside-evidence check. It changes how work is
distributed, never the discipline.

### 4. Close

After the middle segment, compare `actual` with the proposal and summarise: tokens and time
against the estimate, re-shapes, loops that hit a cap. Present the back gate (or
the `verify: auto` result), then the merge under the external-write gate.

## Shape-selection rubric

For each remaining checkpoint, in this order:

1. **Skip-gate first.** Run `parallelism.md`'s skip-gate against this feature's
   real work: N < 2, units that share context, units that depend on each other,
   a human sign-off between them, or work cheaper to do than to dispatch. If it
   hits, the checkpoint is a **Chain** node (Tier 1). Most checkpoints of most
   features land here, and that is correct.
2. **Only if the skip-gate passes,** choose the shape from the real units:
   independent units become a Fan-out or Diamond, a confidence need becomes a
   Star or Tree, and a target to reach becomes a Loop or Feedback. Use the
   pipeline table in `graph-shapes.md` as the prior.
3. **Name the dynamic slot** and hardcode every other edge.
4. **Name the outside evidence** for every fan-out: which tool run, or which
   human gate.
5. **Declare the cap** for every loop (see below).
6. **Pick the model class** per node with the three questions in
   `${CLAUDE_PLUGIN_ROOT}/references/model-classes.md`. Record the class, never a
   product name. Resolve it against the Agent tool's live `model` enum at
   dispatch. `dae_graph.py` rejects product names, and `frontier` on a loop.

**Yield nodes.** A panel, a set of lenses, a gauntlet critic or a set of formal
checks is a node with `yield_of: <parent-id>`. Its shape, class, cap and outside
evidence are declared and validated like any other node's, but it writes no
handoff. The parent's handoff and the parent's checks cover it. A CP5 feature
with a `gauntlet:` bar gets its own Feedback yield node with its own
`max_rounds`, separate from the green loop.

Per-checkpoint priors, re-derived every run:

| CP | Node(s) | Usual shape | Role agent / skill |
|---|---|---|---|
| 2 | discover-acs, then the review panel | Chain, then a Star (yielded) | `/engineer.discover-acs`; `engineer:panel-adviser` + `engineer:panel-advocate` |
| 3 | atdd | Chain | `/engineer.atdd` |
| 4 | plan, then the review panel | Chain (Tree if design angles fan out), then a Star | `/engineer.plan`; panel agents |
| 5 | implement | Loop (green loop), then Feedback if a `gauntlet:` bar exists | `atdd:atdd-team` (Phase 4 only); `engineer:gauntlet-critic` |
| 6 | refine | Diamond of lenses (yielded), verified by a test re-run | `/engineer.refine`; `engineer:reviewer` ×3 |
| 7 | verify | Star of tools | `engineer:verifier` |
| 8 | harden | Branch (the advisor), then a Diamond of the picked tools | `/engineer.harden`; `engineer:formal-verifier` |

## Loop caps

The rule is in `graph-shapes.md`. These are the numbers each loop declares:

| Loop | `max_rounds` | `no_progress` |
|---|---|---|
| CP5 green loop | 2 × acceptance tests failing at the start | `stuck_loop_threshold` rounds with no test turning green |
| CP5 gauntlet | per `gauntlet.md` | per `gauntlet.md` |
| CP8 kill mutants | survivors at the start | a round kills nothing |
| Node retry (failure handling) | 1 | — (a retry is a single attempt) |

When a loop is capped, stop the segment. Never start a second loop over the same
work to get around the cap.

## Estimates

The estimates are priors. Calibrate them against `actual:` in the last two or
three features' `run-graph.yml`, not all of them:

- **tokens** = Σ over nodes of (agents × per-agent prior). Rough priors are
  20–50k for an `economy` script-wrapper, 100–300k for an `inherit` skill node,
  50–100k per review lens or panel role, and 50–150k per loop round, multiplied
  by the cap as the ceiling. Show the expected value and the ceiling.
- **wall-clock** = a Chain adds its nodes' times, a fan-out takes the slowest
  branch, and a loop multiplies its round time by its expected rounds.

Say "rough" in the proposal. An estimate that hides its uncertainty is worse
than none.

## The node brief

Use the template in `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md`,
including the reporting contract and the role agent's `subagent_type` when one
fits. Add these lines to Constraints:

```
  - coordinated: true. You are node <node-id> of run-graph.yml. Follow
    "Coordinated nodes" in references/handoff-dispatch.md: write your handoff,
    do not dispatch the next checkpoint, do not ask the human, and yield
    instead of spawning subagents.
  - agent_id: <run-<node-id>-<attempt>>. Write exactly this in your handoff.
  - Loop cap (loop nodes only): max_rounds <N>; stop on <no_progress>.
  - Return: the handoff path, plus one line on anything the graph did not
    expect (N different from <expected>, a unit that would not decompose).
```

## Stop rules: the only times the coordinator stops

1. **A human gate**: front or back, per the Segments table.
2. **`autonomy_level: low`**: confirm before each dispatch, plus the
   per-checkpoint gates.
3. **The external-write gate**: push, PR, merge, comment.
4. **A node's handoff sets `human_action_needed: yes`** mid-segment: a loop cap,
   an unaddressed `error` panel finding, or a spec that looks wrong.
5. **Failure that a re-shape cannot fix** (below).
6. **Infrastructure** that `dae_infra.py ensure` could not start.
7. **A `dae_graph.py` failure** after a re-shape that you cannot repair.

Nothing else stops the run. A mechanical choice is not a reason to ask; see
`handoff-dispatch.md`.

## Failure handling: never continue silently

A node has failed, or **returned less** than it should, when:

- there is no handoff, it has `status: interrupted`, or an exit criterion is
  unmet or `partial`;
- `dae_handoff.py` or `dae_ontology.py` fails;
- the reply says the work was not done, or covers fewer units than the brief
  named (8 of 12 files reviewed);
- a fan-out branch returned nothing, or the outside-evidence check did not run.

Then, in order:

1. **Retry once** with a fresh agent (`attempt` + 1, the same brief), but only
   if the cause looks transient: a crash, a timeout, or a substrate that was
   unavailable. One retry, never more.
2. **Re-shape** when the graph was wrong for the work. Example: a fan-out unit
   was not actually independent, so make it a Chain. Record the re-shape and
   continue.
3. **Surface it** otherwise. Stop, name the node, what came back and what was
   missing, and recommend a next step. The rest of the graph does not run on
   top of a hole.

Never mark a checkpoint done, fill in a missing result yourself, or move to the
next node on a partial result. A plausible reconstruction is worse than a stop,
because downstream nodes act on it.

## `run-graph.yml`

```yaml
feature: 012-checkout-coupons
proposed: 2026-10-06T1530
autonomy: medium
front: bundled                      # bundled | auto | per-checkpoint
segments:
  - name: front
    checkpoints: [2, 3, 4]
    tier: 2
    nodes:
      - id: acs
        cp: 2
        role: /engineer.discover-acs
        shape: chain
        model: inherit
      - id: acs-panel
        cp: 2
        yield_of: acs
        role: engineer:panel-adviser + engineer:panel-advocate
        shape: star
        model: frontier
        verified_by: human          # the front gate
      - id: spec
        cp: 3
        role: /engineer.atdd
        shape: chain
        model: inherit
      - id: plan
        cp: 4
        role: /engineer.plan
        shape: chain
        model: inherit
    estimate:
      tokens: 600000
      tokens_ceiling: 900000
      minutes: 35
  - name: middle
    checkpoints: [5, 6, 7, 8]
    tier: 2
    nodes:
      - id: build
        cp: 5
        role: atdd:atdd-team
        shape: loop
        model: inherit
        max_rounds: 14              # 2 × 7 failing scenarios
        no_progress: stuck_loop_threshold
        verified_by: tool           # the acceptance + unit run
      - id: gauntlet
        cp: 5
        yield_of: build
        role: engineer:gauntlet-critic
        shape: feedback
        model: inherit
        max_rounds: 5
        no_progress: same gap twice
        verified_by: tool           # the captured bar
      - id: refine
        cp: 6
        role: /engineer.refine
        shape: diamond
        model: inherit
        verified_by: tool           # tests re-run after the edits
      - id: verify
        cp: 7
        role: engineer:verifier
        shape: star
        model: frontier
        verified_by: tool           # dae_arch + crap-analyzer
      - id: harden
        cp: 8
        role: /engineer.harden
        shape: branch
        model: inherit
    estimate:
      tokens: 900000
      tokens_ceiling: 1600000
      minutes: 60
reshapes: []
actual: []
```

Block YAML only (no `{…}` flow maps); `dae_graph.py` reads it with the kit's
stdlib parser. The validator reads `front`, the segments, and per node `id`,
`cp`, `yield_of`, `shape`, `model`, `max_rounds`, `no_progress` and
`verified_by`. Everything else (`role`, `tier`, `estimate`, `reshapes`,
`actual`) is the record a human compares afterwards. This file is how the proposal can be compared with the actual run
afterwards.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/run/SKILL.md`: the entry point
- `${CLAUDE_PLUGIN_ROOT}/references/graph-shapes.md`: shapes, the loop rule, outside evidence
- `${CLAUDE_PLUGIN_ROOT}/references/parallelism.md`: the skip-gate, tiers, degradation
- `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md`: brief template, reporting contract, coordinated nodes, external-write gate
- `${CLAUDE_PLUGIN_ROOT}/references/gate-profile.md`: the front and verify dials
- `${CLAUDE_PLUGIN_ROOT}/references/choice-points.md`: how the proposal and the gates are rendered
- `${CLAUDE_PLUGIN_ROOT}/references/model-classes.md`: class resolution
- `${CLAUDE_PLUGIN_ROOT}/scripts/dae_graph.py`: the graph validator
