#!/usr/bin/env python3
"""dae_ship.py — write a feature's done state for the ship commit.

The ship commit is the feature branch's LAST commit before the PR opens, so
`status: done` reaches main exactly when the PR merges. Post-merge then writes
nothing tracked on main.

This helper writes the deterministic part, and only on the working tree:
  - feature.md          status: done
  - progress.md         CP8 row done (full lane) + CURRENT header "awaiting merge"
  - local roadmap       dae_roadmap.py mark <roadmap_ref> shipped (if the feature has one)
The caller (harden / express) stages those plus the verify-app feature-map row and
the in-repo session-summary entry, then makes the commit. merged_at is never
written: it is unknowable before merge (the external tracker sync adds it).

Refuses (exit 1, nothing written) when a full-lane feature lacks a complete CP7
and CP8 handoff: "done" without a verify handoff is the merged-unverified gap,
caught here instead of after the merge. `--lane express` has no numbered CPs
(its deterministic gates are the verifier), so it skips that check.

Usage:
  dae_ship.py <feature-dir> [--lane full|express]
Output: JSON {feature, written: [paths]}. Exit 1 refused, 2 bad dir, 3 usage.
"""
import json
import os
import re
import sys

import dae_handoff
import dae_reconcile
import dae_roadmap

_HEADER = "> ▶ CP8 Harden — awaiting merge | NEXT: open PR / merge | BLOCKED: none"
_CP8_ROW = re.compile(r"^(\|\s*8\s*\|[^|]*\|)[^|]*(\|.*)$", re.MULTILINE)
_HEADER_LINE = re.compile(r"^>?\s*▶.*$", re.MULTILINE)


class ShipRefused(Exception):
    pass


def set_progress(text, full_lane=True):
    """progress.md text with CP8 row done (full lane) and the CURRENT header set."""
    if full_lane:
        if _CP8_ROW.search(text):
            text = _CP8_ROW.sub(r"\1 done \2", text, count=1)
        else:
            text = text.rstrip("\n") + "\n| 8 | Harden | done |\n"
    if _HEADER_LINE.search(text):
        return _HEADER_LINE.sub(_HEADER, text, count=1)
    return _HEADER + "\n\n" + text


def ship(feature_dir, lane="full"):
    fm_path = os.path.join(feature_dir, "feature.md")
    if not os.path.isfile(fm_path):
        raise FileNotFoundError(fm_path)
    full = lane != "express"
    if full:
        for cp in (7, 8):
            ok, msg = dae_handoff.gate(feature_dir, through=cp)
            if not ok:
                raise ShipRefused("refusing done: %s" % msg)

    written = []
    with open(fm_path, encoding="utf-8") as f:
        text = f.read()
    with open(fm_path, "w", encoding="utf-8") as f:
        f.write(dae_reconcile.set_status(text, dae_reconcile.DONE))
    written.append(fm_path)

    prog = os.path.join(feature_dir, "progress.md")
    old = open(prog, encoding="utf-8").read() if os.path.isfile(prog) else ""
    with open(prog, "w", encoding="utf-8") as f:
        f.write(set_progress(old, full))
    written.append(prog)

    m = re.search(r"^roadmap_ref:[ \t]*(\S+)", text, re.MULTILINE)
    slug = os.path.basename(os.path.normpath(feature_dir))
    if m and dae_roadmap.mark(feature_dir, m.group(1), "shipped", slug):
        written.append(dae_roadmap.roadmap_path(feature_dir))
    return {"feature": slug, "written": written}


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    lane = argv[argv.index("--lane") + 1] if "--lane" in argv[1:] else "full"
    try:
        print(json.dumps(ship(argv[0], lane)))
    except ShipRefused as exc:
        sys.stderr.write("%s\n" % exc)
        return 1
    except FileNotFoundError as exc:
        sys.stderr.write("missing %s\n" % exc)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
