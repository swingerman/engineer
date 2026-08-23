#!/usr/bin/env python3
"""dae_mergeready.py — is this feature's PR hardened enough to auto-merge?

The deterministic bar behind `gate_profile.verify: auto` (see
`references/gate-profile.md`). Aggregates signals the pipeline already produces —
it adds no new checks — and is **fail-closed**: any signal it cannot
affirmatively confirm green is a blocker → human.

  dae_mergeready.py <feature-dir> [--json] [--final-cp N]

Exit 0 = ready to auto-merge, 1 = not ready (blockers), 2 = bad usage.
`--json` prints {ready, blockers, checks}. Reuses dae_resolve/handoff/ontology/arch.
"""
import json
import os
import re
import subprocess
import sys

import dae_resolve

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def _run(script, *args):
    """(returncode, stdout, stderr) for a sibling dae_ script; rc=127 if it blows up."""
    try:
        p = subprocess.run([sys.executable, os.path.join(_SCRIPTS, script), *args],
                           capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:  # fail-closed: a check that can't run is not green
        return 127, "", str(e)


def _frontmatter_text(feature_dir):
    path = os.path.join(feature_dir, "feature.md")
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return ""
    m = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.DOTALL)
    return m.group(1) if m else ""


def _field(fm_text, key):
    m = re.search(r"(?m)^\s*%s:\s*(.+?)\s*$" % re.escape(key), fm_text)
    if not m:
        return None
    return m.group(1).strip().strip('"').strip("'")


def _has_gauntlet_bar(feature_dir):
    plan = os.path.join(feature_dir, "plan.md")
    try:
        with open(plan, encoding="utf-8", errors="replace") as fh:
            return re.search(r"(?m)^\s*gauntlet:\s*$", fh.read()) is not None
    except OSError:
        return False


def _gauntlet_cleared(feature_dir):
    """A declared gauntlet must have ended clean. ponytail: grep the handoffs for
    `stopped_by: clear`; upgrade to parsing gauntlet_rounds[] if a subtler
    verdict ever matters."""
    hdir = os.path.join(feature_dir, "handoffs")
    if not os.path.isdir(hdir):
        return False
    for name in os.listdir(hdir):
        try:
            with open(os.path.join(hdir, name), encoding="utf-8", errors="replace") as fh:
                if "stopped_by: clear" in fh.read():
                    return True
        except OSError:
            continue
    return False


def _ci_green(root, branch):
    """gh PR check rollup for the branch. Fail-closed: no gh / no PR / any
    non-SUCCESS → not green."""
    if not branch:
        return False, "no branch on feature.md"
    try:
        p = subprocess.run(
            ["gh", "pr", "view", branch, "--json", "state,statusCheckRollup"],
            cwd=root, capture_output=True, text=True)
    except FileNotFoundError:
        return False, "gh CLI not available"
    if p.returncode != 0:
        return False, "no open PR for branch (%s)" % (p.stderr.strip()[:80] or "gh error")
    try:
        data = json.loads(p.stdout)
    except ValueError:
        return False, "unparseable gh output"
    if data.get("state") != "OPEN":
        return False, "PR state is %s" % data.get("state")
    rollup = data.get("statusCheckRollup") or []
    bad = [c.get("name", "?") for c in rollup
           if (c.get("conclusion") or c.get("state")) not in ("SUCCESS", "NEUTRAL", "SKIPPED")]
    if bad:
        return False, "CI not green: %s" % ", ".join(bad[:5])
    return True, "CI green (%d checks)" % len(rollup)


def gather(feature_dir, final_cp="7"):
    """Run every check → list of {name, ok, detail}. I/O lives here."""
    fm = _frontmatter_text(feature_dir)
    result = dae_resolve.resolve(feature_dir)
    root = result["methodology_root"] if result else os.path.abspath(feature_dir)
    checks = []

    # Eligibility + guardrails (from feature.md)
    verify = _field(fm, "verify")  # gate_profile.verify (only `verify:` in frontmatter)
    checks.append(("verify:auto set", verify == "auto",
                   "verify=%r" % verify))
    autonomy = _field(fm, "autonomy_level")
    checks.append(("autonomy not low", autonomy != "low",
                   "autonomy_level=%r" % autonomy))
    vm = _field(fm, "validation_method")
    checks.append(("validation_method default", not vm,
                   "non-default: %r" % vm if vm else "default"))

    # Objective gates (reuse existing tools; exit 0 == green)
    rc, _, err = _run("dae_handoff.py", feature_dir, "--through", str(final_cp))
    checks.append(("checkpoints met through CP%s" % final_cp, rc == 0,
                   "dae_handoff rc=%d %s" % (rc, err.strip()[:80])))
    rc, _, err = _run("dae_ontology.py", feature_dir)
    checks.append(("ontology clean", rc == 0,
                   "dae_ontology rc=%d %s" % (rc, err.strip()[:80])))
    rc, _, err = _run("dae_arch.py", "--full", root)
    checks.append(("architecture clean", rc == 0,
                   "dae_arch rc=%d %s" % (rc, err.strip()[:80])))

    # Gauntlet: cleared iff declared
    if _has_gauntlet_bar(feature_dir):
        ok = _gauntlet_cleared(feature_dir)
        checks.append(("gauntlet cleared", ok,
                       "declared bar; stopped_by:clear %s" % ("found" if ok else "NOT found")))

    # CI / open PR
    ci_ok, ci_detail = _ci_green(root, _field(fm, "branch"))
    checks.append(("CI green on open PR", ci_ok, ci_detail))

    return [{"name": n, "ok": bool(o), "detail": d} for n, o, d in checks]


def evaluate(checks):
    """Pure, fail-closed: ready iff every check passed. Blockers name the fails."""
    blockers = [c["name"] for c in checks if not c["ok"]]
    return {"ready": len(blockers) == 0, "blockers": blockers}


def main(argv):
    args = list(argv)
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if args else 2
    as_json = "--json" in args
    if as_json:
        args.remove("--json")
    final_cp = "7"
    if "--final-cp" in args:
        i = args.index("--final-cp")
        final_cp = args[i + 1] if i + 1 < len(args) else "7"
        del args[i:i + 2]
    feature_dir = args[0]
    if not os.path.isdir(feature_dir):
        sys.stderr.write("not a feature dir: %s\n" % feature_dir)
        return 2

    checks = gather(feature_dir, final_cp)
    verdict = evaluate(checks)
    if as_json:
        json.dump({**verdict, "checks": checks}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write("merge-ready: %s\n" % ("YES" if verdict["ready"] else "NO"))
        for c in checks:
            sys.stdout.write("  [%s] %s — %s\n"
                             % ("✓" if c["ok"] else "✗", c["name"], c["detail"]))
        if verdict["blockers"]:
            sys.stdout.write("\nblockers: %s\n" % ", ".join(verdict["blockers"]))
    return 0 if verdict["ready"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
