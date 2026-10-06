---
name: run
description: Use to drive one feature from CP2 to CP8 under a coordinator. It proposes the feature's agent graph (shapes, model classes, loop caps, cost estimate), then dispatches every checkpoint as a fresh agent, stopping only at the front and back human gates. Triggers — "/engineer.run <feature>", "run this feature end to end", "drive the feature", "coordinate the pipeline", "build it through to verify".
---

# run

One coordinator per feature, CP2 → CP8. The coordinator is the graph's one
model-decided node: it **chooses** the graph (shapes, model class per node, loop
caps), records the choice, and then follows fixed edges. Each checkpoint runs as
a fresh agent, and the coordinator never reads source code.

Your standing instructions are `${CLAUDE_PLUGIN_ROOT}/references/coordinator.md`.
Read it in full before step 1. This file is only the entry point.

## When to use

- A Ready feature (CP1.5) that you want driven through the pipeline with only
  the front and back gates as human stops.
- A half-done feature: the run resumes from the latest complete checkpoint.

**Not for:**
- Several features at once. Use Decarchy, one coordinator per worktree.
- A single checkpoint. Call that skill directly; every skill still works
  standalone, exactly as before.
- An XS feature. The run branches to `/engineer.express` at entry.

## Workflow

0. **Resolve.** Root and manifest (`${CLAUDE_PLUGIN_ROOT}/scripts/dae_resolve.py`).
   If `<feature>` has no folder, run `/engineer.feature-init` first. If
   `gate_profile.lane: express`, invoke `/engineer.express` and stop.
   Enforce the branch (`dae_branch.py`). Find the resume point with
   `dae_handoff.py <feature-dir>`.
1. **Shape.** Build the graph (coordinator.md, *Shape-selection rubric*), write
   `features/NNN-<slug>/run-graph.yml`, and validate it with
   `${CLAUDE_PLUGIN_ROOT}/scripts/dae_graph.py`. Do not run a graph that fails
   validation.
2. **Propose**, as a choice point together with the front gate (coordinator.md,
   step 1): the graph, each node's role, class and cap, and rough tokens and
   wall-clock per segment.
3. **Run** the segments with the dispatch loop (coordinator.md, step 2): brief
   each node with `coordinated: true`, serve its yields, check the outside
   evidence after each node, and record `actual:`. Re-shape on drift and report
   it (ask only at `low`).
4. **Gates.** Stop at the front gate and the back gate as `gate_profile` and
   `autonomy_level` dictate. Everything else in the middle runs without asking.
5. **Close.** Compare the actual run with the proposal, present the back gate,
   then the merge under the external-write gate.

## Handoff

The coordinator writes **no checkpoint handoffs**: each node writes its own.
At the close (or when a stop rule fires), emit one handoff per
`${CLAUDE_PLUGIN_ROOT}/references/handoff-summary.md` with `skill: run`,
`checkpoint: null`, `artifacts: [features/NNN-<slug>/run-graph.yml]`, a
`findings_summary` of estimate vs actual, and `recommended_next` (the gate
waiting, or "done").

## References

- `${CLAUDE_PLUGIN_ROOT}/references/coordinator.md`: the standing instructions
- `${CLAUDE_PLUGIN_ROOT}/references/graph-shapes.md`: shape vocabulary, the loop rule, outside evidence
- `${CLAUDE_PLUGIN_ROOT}/references/handoff-dispatch.md`: "Coordinated nodes", the brief template
- `${CLAUDE_PLUGIN_ROOT}/scripts/dae_graph.py`: graph validator
