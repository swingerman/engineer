#!/usr/bin/env python3
"""dae_feature_number.py — allocate the next feature number (NNN).

Scanning only the current checkout's `features/` collides with numbers taken
on other unmerged work. So the max NNN is taken across:
  - the features dir in every git worktree (on disk — uncommitted folders count)
  - the features dir in every local and remote-tracking branch (committed trees)
Outside a git repo it falls back to the local features dir alone.

Usage:
  dae_feature_number.py [START_DIR]   prints the next number, 3-digit zero-padded
"""
import os
import re
import subprocess
import sys

import dae_resolve

_NNN_RE = re.compile(r"^(\d+)-")


def _numbers(names):
    return {int(m.group(1)) for m in map(_NNN_RE.match, names) if m}


def _git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                       text=True, check=False)
    return r.stdout if r.returncode == 0 else None


def taken_numbers(features_dir):
    """Every NNN used under features_dir across all worktrees and branches."""
    taken = _numbers(os.listdir(features_dir)) if os.path.isdir(features_dir) else set()
    top = _git(os.path.dirname(os.path.abspath(features_dir)), "rev-parse", "--show-toplevel")
    if top is None:
        return taken
    top = top.strip()
    rel = os.path.relpath(os.path.realpath(features_dir), os.path.realpath(top))

    for line in (_git(top, "worktree", "list", "--porcelain") or "").splitlines():
        if line.startswith("worktree "):
            d = os.path.join(line[len("worktree "):], rel)
            if os.path.isdir(d):
                taken |= _numbers(os.listdir(d))

    refs = (_git(top, "for-each-ref", "--format=%(refname)",
                 "refs/heads", "refs/remotes") or "").split()
    for ref in refs:
        out = _git(top, "ls-tree", "--name-only", "%s:%s" % (ref, rel))
        if out:
            taken |= _numbers(out.splitlines())
    return taken


def next_number(features_dir):
    return "%03d" % (max(taken_numbers(features_dir), default=0) + 1)


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    root, manifest_path = dae_resolve.find_methodology_root(argv[0] if argv else os.getcwd())
    if root is None:
        print("no .engineer/manifest.yml found -- run /engineer.onboard", file=sys.stderr)
        return 2
    manifest = {}
    with open(manifest_path, encoding="utf-8") as f:
        try:
            manifest = dae_resolve.read_manifest(f.read())
        except dae_resolve.ManifestError:
            pass
    print(next_number(os.path.join(root, manifest.get("features_root") or "features/")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
