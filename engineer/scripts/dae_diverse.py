#!/usr/bin/env python3
"""dae_diverse.py — does this feature get a second-family review?

Answers ONE question from feature.md, so no skill decides it by judgment:
should the CP2/CP4 advocate and a second CP7 verifier run on the `diverse`
model class (references/model-classes.md)?

  yes  size L/XL, or `charter_flagged: true`
  no   size XS/S or `lane: express` — always, flagged or not (cost rule)
  no   everything else (M, no size)

Usage:
    dae_diverse.py <feature-dir>

Output: JSON {diverse, reason}. Exit 0 (advisory), 2 if no feature.md.
"""

import json
import sys

from dae_delegable import load_frontmatter


def evaluate(fm):
    """Pure gate. fm: feature.md frontmatter dict → (bool, reason)."""
    size = str(fm.get("size", "")).upper()
    gp = fm.get("gate_profile") if isinstance(fm.get("gate_profile"), dict) else {}
    if str(gp.get("lane", fm.get("lane", ""))).lower() == "express":
        return False, "express lane — never diverse"
    if size in ("XS", "S"):
        return False, "size %s — never diverse" % size
    if size in ("L", "XL"):
        return True, "size %s" % size
    if str(fm.get("charter_flagged", "")).lower() == "true":
        return True, "charter-flagged"
    return False, "size %s, not charter-flagged" % (size or "unset")


def main(argv):
    if not argv:
        sys.stderr.write("usage: dae_diverse.py <feature-dir>\n")
        return 2
    fm = load_frontmatter(argv[0])
    if fm is None:
        sys.stderr.write("no feature.md in %s\n" % argv[0])
        return 2
    diverse, reason = evaluate(fm)
    print(json.dumps({"diverse": diverse, "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
