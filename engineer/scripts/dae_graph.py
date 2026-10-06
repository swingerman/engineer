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

import dae_resolve

SHAPES = {"chain", "branch", "fan-out", "fan-in", "diamond", "star", "tree",
          "loop", "feedback", "dag"}
LOOPS = {"loop", "feedback"}
FANS = {"fan-out", "diamond", "star", "tree"}
MODEL_CLASSES = {"economy", "inherit", "frontier"}
OUTSIDE = {"tool", "human"}
# Gate boundaries: a segment's checkpoints all fall in one band.
BANDS = ((2, 3, 4), (5, 6, 7, 8))
PER_CHECKPOINT_BANDS = ((2,), (3, 4), (5, 6, 7, 8))


def _band(cp, bands):
    for i, band in enumerate(bands):
        if cp in band:
            return i
    return None


def check(graph):
    """Return a list of error strings; [] means the graph may run."""
    errors = []
    segments = graph.get("segments") if isinstance(graph, dict) else None
    if not isinstance(segments, list) or not segments:
        return ["no segments"]
    gate_bands = PER_CHECKPOINT_BANDS if graph.get("front") == "per-checkpoint" else BANDS
    for si, seg in enumerate(segments):
        if not isinstance(seg, dict):
            errors.append("segment %d: not a mapping" % si)
            continue
        name = seg.get("name", "segment %d" % si)
        cps = seg.get("checkpoints")
        if not isinstance(cps, list) or not cps or \
                not all(isinstance(cp, int) and not isinstance(cp, bool) for cp in cps):
            errors.append("%s: checkpoints must be a list of integers" % name)
            continue
        bands = {_band(cp, gate_bands) for cp in cps}
        if None in bands:
            errors.append("%s: checkpoint outside CP2-CP8 in %s" % (name, cps))
        elif len(bands) > 1:
            errors.append("%s: spans a human gate (%s) — gate bands are %s"
                          % (name, cps, [list(b) for b in gate_bands]))
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
            if node.get("model", "inherit") not in MODEL_CLASSES:
                errors.append("%s: model %r is not a class (economy|inherit|frontier)"
                              % (nid, node.get("model")))
            if shape in LOOPS:
                cap = node.get("max_rounds")
                if not isinstance(cap, int) or isinstance(cap, bool) or cap < 1:
                    errors.append("%s: loop without a max_rounds cap" % nid)
                if not node.get("no_progress"):
                    errors.append("%s: loop without a no_progress stop" % nid)
                if node.get("model") == "frontier":
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
