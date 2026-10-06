#!/usr/bin/env python3
"""dae_graph.py — validate a feature's run graph (features/NNN-slug/run-graph.yml).

/engineer.run writes the graph it proposes before executing it. This checks the
rules from references/graph-shapes.md mechanically, so a graph that breaks them
cannot run:

  - every segment sits between two human-gate boundaries and never spans one
    (workflows take no mid-run input): the front gate after CP4, plus one after
    CP2 when the graph's `front` is per-checkpoint; the middle runs CP5-CP8 to
    the back gate;
  - a yield node (`yield_of`) names a non-yield node in its own segment;
  - every node names a known shape and a model class;
  - every loop/feedback node declares max_rounds (int >= 1) and no_progress,
    and never runs on the frontier class (it reads a lot and loops: the cost trap);
  - every fan-out/diamond/star/tree node is verified from outside the fan-out
    (verified_by: tool | human).

Usage:
  dae_graph.py <run-graph.yml>    JSON {ok, errors}; exit 1 if any error
"""
import json
import sys

import dae_ontology
import dae_resolve

SHAPES = {"chain", "branch", "fan-out", "fan-in", "diamond", "star", "tree",
          "loop", "feedback", "dag"}
LOOPS = {"loop", "feedback"}
FANS = {"fan-out", "diamond", "star", "tree"}
MODEL_CLASSES = {"economy", "inherit", "frontier"}   # references/model-classes.md
OUTSIDE = {"tool", "human"}   # handoff verified_by values, minus `judgment`
RUN_CHECKPOINTS = {cp for cp in dae_ontology.CHECKPOINTS if cp >= 2}
# Human gates sit after these checkpoints; a segment never contains one.
GATES = {4}
PER_CHECKPOINT_GATES = {2, 4}


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def check(graph):
    """Return a list of error strings; [] means the graph may run."""
    errors = []
    segments = graph.get("segments") if isinstance(graph, dict) else None
    if not isinstance(segments, list) or not segments:
        return ["no segments"]
    gates = PER_CHECKPOINT_GATES if graph.get("front") == "per-checkpoint" else GATES
    for si, seg in enumerate(segments):
        if not isinstance(seg, dict):
            errors.append("segment %d: not a mapping" % si)
            continue
        name = seg.get("name", "segment %d" % si)
        cps = seg.get("checkpoints")
        if not isinstance(cps, list) or not cps or not all(_int(cp) for cp in cps):
            errors.append("%s: checkpoints must be a list of integers" % name)
            continue
        if not set(cps) <= RUN_CHECKPOINTS:
            errors.append("%s: checkpoint outside CP2-CP8 in %s" % (name, cps))
        elif len({sum(g < cp for g in gates) for cp in cps}) > 1:
            errors.append("%s: spans a human gate (%s) — gates sit after CP%s"
                          % (name, cps, sorted(gates)))
        nodes = seg.get("nodes")
        if not isinstance(nodes, list) or not nodes or \
                not all(isinstance(n, dict) for n in nodes):
            errors.append("%s: nodes must be a non-empty list of mappings" % name)
            continue
        parents = {n.get("id") for n in nodes if not n.get("yield_of")}
        for ni, node in enumerate(nodes):
            nid = "%s/%s" % (name, node.get("id", ni))
            if node.get("yield_of") and node["yield_of"] not in parents:
                errors.append("%s: yield_of %r is not a node in this segment"
                              % (nid, node["yield_of"]))
            if node.get("cp") not in cps:
                errors.append("%s: cp %r is not in the segment" % (nid, node.get("cp")))
            shape = node.get("shape")
            if shape not in SHAPES:
                errors.append("%s: unknown shape %r" % (nid, shape))
            model = node.get("model", "inherit")
            if model not in MODEL_CLASSES:
                errors.append("%s: model %r is not a class (economy|inherit|frontier)"
                              % (nid, model))
            if shape in LOOPS:
                cap = node.get("max_rounds")
                if not _int(cap) or cap < 1:
                    errors.append("%s: loop without a max_rounds cap" % nid)
                if not node.get("no_progress"):
                    errors.append("%s: loop without a no_progress stop" % nid)
                if model == "frontier":
                    errors.append("%s: frontier on a loop — use inherit" % nid)
            if shape in FANS and node.get("verified_by") not in OUTSIDE:
                errors.append("%s: %s not verified from outside the fan-out "
                              "(verified_by: tool|human)" % (nid, shape))
    return errors


def main(argv):
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    try:
        with open(argv[0], encoding="utf-8") as f:
            errors = check(dae_resolve.read_manifest(f.read()))
    except (OSError, ValueError) as e:
        errors = ["cannot read graph: %s" % e]
    print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
