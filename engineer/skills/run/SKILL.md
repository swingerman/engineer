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

Execute `coordinator.md` from "The run". In short: resolve the feature (XS goes
to `/engineer.express`), propose a graph that `dae_graph.py` accepts, run its
segments, stop only at the gates, and compare the actual run with the proposal
at the close.

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
