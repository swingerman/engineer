#!/usr/bin/env python3
"""dae_reconcile.py — reconcile a feature's local DAE state with merged-PR reality.

The gap this closes: when a feature's PR merges, `post-merge` updates the
tracker, but nothing flips the *local* `feature.md` status. `progress-log`
derives the tracker record FROM local truth, and `next`/`reorient` survey
`feature.md status` — so a merged feature can sit `in-progress` indefinitely
(nexthq 005 sat `in-progress` ~7 weeks post-merge), poisoning every survey.

Merge detection is `gh`-first so it covers the two cases the git-only ancestry
check (`git merge-base --is-ancestor`) misses:
  - squash-merge — the branch commits are NOT ancestors of main, but the PR is MERGED.
  - git.manual   — the merge happened outside the DAE flow; gh still knows.
Git ancestry is the fallback when `gh` is unavailable.

BACKSTOP ONLY. Features that went through the ship commit (dae_ship.py) already
carry `status: done` on main when the PR merges, so reconcile is a no-op for
them (`needs_reconcile: false`; post-merge runs it read-only to report). `--apply`
is for legacy, onboarded and git.manual features that never got a ship commit;
those are the only cases that still need a commit on main.

Reconcile writes ONLY `feature.md` status (the authoritative field). It does NOT
touch progress.md — that stays `progress-log`'s job (own the file, recompute the
CURRENT header). A merge with no verification handoff (CP7 not done) is FLAGGED
`merged-unverified`: shipped without its ACs verified.

Usage:
  dae_reconcile.py <feature-dir>            detect + report (read-only JSON)
  dae_reconcile.py <feature-dir> --apply    if merged & not done, flip status -> done

Output: JSON {feature, merged, state, pr_number, pr_url, merged_at, source,
current_status, verified, needs_reconcile, flag, applied, new_status}.
Exit 0 (advisory — a "not merged" verdict is a normal result, not an error).
Exit 2 on a missing feature dir / feature.md; 3 on usage error.
"""
import json
import os
import re
import subprocess
import sys

import dae_branch
import dae_handoff
import dae_resolve

DONE = "done"
_STATUS_LINE_RE = re.compile(r"^status:[ \t]*.*$", re.MULTILINE)
_STATUS_VAL_RE = re.compile(r"^status:[ \t]*(\S+)", re.MULTILINE)


class ReconcileError(Exception):
    pass


def _run(cmd, cwd, timeout=20):
    """Run a command; return (returncode, stdout) or (None, '') if it can't run."""
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    return r.returncode, r.stdout


def feature_status(feature_dir):
    """The feature.md frontmatter `status:`, or None if absent."""
    fm_path = os.path.join(feature_dir, "feature.md")
    if not os.path.isfile(fm_path):
        return None
    with open(fm_path, encoding="utf-8") as f:
        fm = dae_resolve.extract_frontmatter(f.read())
    if not fm:
        return None
    m = _STATUS_VAL_RE.search(fm)
    return m.group(1) if m else None


def is_verified(feature_dir):
    """True when CP7 (Verify) is marked done in progress.md — the proxy for
    'the ACs were verified before ship'."""
    p = os.path.join(feature_dir, "progress.md")
    if not os.path.isfile(p):
        return False
    with open(p, encoding="utf-8") as f:
        done = dae_handoff.read_progress(f.read())
    return any(v and _as_num(k) == 7 for k, v in done.items())


def _as_num(k):
    try:
        return float(k)
    except (TypeError, ValueError):
        return None


def pr_merge_state(feature_dir):
    """Detect whether the feature's branch has a merged PR.

    Returns {merged, state, pr_number, pr_url, merged_at, source}. `source` is
    'gh' when GitHub answered, 'git' when only the ancestry fallback did, or
    'unknown' when neither could tell."""
    branch = dae_branch.expected_branch(feature_dir)
    out = {"merged": False, "state": None, "pr_number": None, "pr_url": None,
           "merged_at": None, "source": "unknown", "branch": branch}

    rc, stdout = _run(
        ["gh", "pr", "list", "--head", branch, "--state", "all",
         "--json", "number,state,mergedAt,url", "--limit", "10"],
        cwd=feature_dir)
    if rc == 0 and stdout.strip():
        try:
            prs = json.loads(stdout)
        except ValueError:
            prs = []
        merged = [p for p in prs if p.get("state") == "MERGED"]
        chosen = merged[0] if merged else (prs[0] if prs else None)
        if chosen is not None:
            out["source"] = "gh"
            out["state"] = chosen.get("state")
            out["pr_number"] = chosen.get("number")
            out["pr_url"] = chosen.get("url")
            out["merged_at"] = chosen.get("mergedAt")
            out["merged"] = chosen.get("state") == "MERGED"
            if out["merged"]:
                return out

    # Fallback: git ancestry (only catches non-squash merges whose ref survives).
    for ref in ("origin/%s" % branch, branch):
        rc, _ = _run(["git", "merge-base", "--is-ancestor", ref, "origin/HEAD"],
                    cwd=feature_dir)
        if rc == 0:
            out["merged"] = True
            if out["source"] == "unknown":
                out["source"] = "git"
                out["state"] = "MERGED"
            return out
    return out


def set_status(text, new_status):
    """Return feature.md text with its frontmatter `status:` set to new_status.
    Touches only the status line in the first frontmatter block."""
    fm = dae_resolve.extract_frontmatter(text)
    if not fm:
        raise ReconcileError("feature.md has no frontmatter")
    if _STATUS_LINE_RE.search(fm):
        new_fm = _STATUS_LINE_RE.sub("status: %s" % new_status, fm, count=1)
    else:
        new_fm = fm.rstrip("\n") + "\nstatus: %s\n" % new_status
    return text.replace(fm, new_fm, 1)


def reconcile(feature_dir, apply=False):
    """Detect merge state and, if apply and merged-but-not-done, flip
    feature.md status -> done. Returns the structured result dict."""
    if not os.path.isdir(feature_dir):
        raise ReconcileError("no such feature dir: %s" % feature_dir)
    fm_path = os.path.join(feature_dir, "feature.md")
    if not os.path.isfile(fm_path):
        raise ReconcileError("no feature.md in %s" % feature_dir)

    state = pr_merge_state(feature_dir)
    status = feature_status(feature_dir)
    verified = is_verified(feature_dir)
    needs = bool(state["merged"]) and status != DONE

    result = {
        "feature": os.path.basename(os.path.normpath(feature_dir)),
        "merged": state["merged"],
        "state": state["state"],
        "pr_number": state["pr_number"],
        "pr_url": state["pr_url"],
        "merged_at": state["merged_at"],
        "source": state["source"],
        "branch": state["branch"],
        "current_status": status,
        "verified": verified,
        "needs_reconcile": needs,
        "flag": ("merged-unverified" if needs and not verified else None),
        "applied": False,
        "new_status": None,
    }

    if apply and needs:
        with open(fm_path, encoding="utf-8") as f:
            text = f.read()
        with open(fm_path, "w", encoding="utf-8") as f:
            f.write(set_status(text, DONE))
        result["applied"] = True
        result["new_status"] = DONE

    return result


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    apply = "--apply" in argv[1:]
    feature_dir = argv[0]
    try:
        result = reconcile(feature_dir, apply=apply)
    except ReconcileError as exc:
        sys.stderr.write("%s\n" % exc)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
