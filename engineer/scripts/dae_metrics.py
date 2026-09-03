#!/usr/bin/env python3
"""dae_metrics.py — DORA + governance metrics from the artifacts DAE already writes.

The governance/metrics layer the AI-native SDLC playbook asks for, computed from
git + handoffs + .engineer/fixes/. Fail-graceful: any metric whose data is absent
is null, never a crash. stdlib-only.

  dae_metrics.py [START_DIR] [--window N] [--json]

`--window` (days, default 90) scopes the operational metrics (deploy frequency,
change-failure rate). Lead time and MTTR are all-time medians so they populate
even on a quiet repo. Reuses dae_resolve.
"""
import json
import os
import re
import statistics
import subprocess
import sys
import time

import dae_dashboard
import dae_resolve

_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
DAY = 86400


def _git(root, *args):
    try:
        p = subprocess.run(["git", "-C", root, *args],
                           capture_output=True, text=True, timeout=20)
        return p.stdout if p.returncode == 0 else ""
    except Exception:
        return ""


def _deploys(root, since_ts):
    """Merge commits on the current branch since `since_ts` (a deploy proxy)."""
    out = _git(root, "log", "--merges", "--first-parent", "--format=%ct")
    return [int(t) for t in out.split() if t.isdigit() and int(t) >= since_ts]


def _feature_lead_times(root):
    """Per shipped feature: created-date -> newest-handoff mtime, in days."""
    fdir = os.path.join(root, "features")
    days = []
    if not os.path.isdir(fdir):
        return days
    for name in sorted(os.listdir(fdir)):
        d = os.path.join(fdir, name)
        fm_path = os.path.join(d, "feature.md")
        if not os.path.isfile(fm_path):
            continue
        with open(fm_path, encoding="utf-8", errors="replace") as fh:
            fm = dae_dashboard._frontmatter(fh.read())
        if (fm.get("status") or "").lower() not in ("done", "merged-unverified"):
            continue
        m = _DATE_RE.search(fm.get("created", ""))
        if not m:
            continue
        created = time.mktime((int(m.group(1)), int(m.group(2)), int(m.group(3)),
                               0, 0, 0, 0, 0, -1))
        hdir = os.path.join(d, "handoffs")
        last = None
        if os.path.isdir(hdir):
            mtimes = [os.path.getmtime(os.path.join(hdir, h))
                      for h in os.listdir(hdir) if h.endswith(".md")]
            if mtimes:
                last = max(mtimes)
        if last and last >= created:
            days.append((last - created) / DAY)
    return days


def _fix_stats(root, since_ts):
    """(.engineer/fixes) -> lead each fix's report date (filename) + close (mtime).
    Returns (fixes_in_window, mttr_days_all)."""
    fdir = os.path.join(root, ".engineer", "fixes")
    in_window = 0
    mttr = []
    if not os.path.isdir(fdir):
        return in_window, mttr
    for name in os.listdir(fdir):
        if not name.endswith(".md"):
            continue
        m = _DATE_RE.match(name)
        if not m:
            continue
        report = time.mktime((int(m.group(1)), int(m.group(2)), int(m.group(3)),
                              0, 0, 0, 0, 0, -1))
        if report >= since_ts:
            in_window += 1
        close = os.path.getmtime(os.path.join(fdir, name))  # ponytail: mtime ~= close time
        if close >= report:
            mttr.append((close - report) / DAY)
    return in_window, mttr


def _governance(root):
    """Per-feature artifact versions (handoff count) + last-touched."""
    fdir = os.path.join(root, "features")
    rows = []
    if not os.path.isdir(fdir):
        return rows
    for name in sorted(os.listdir(fdir)):
        hdir = os.path.join(fdir, name, "handoffs")
        if not os.path.isdir(hdir):
            continue
        hs = [h for h in os.listdir(hdir) if h.endswith(".md")]
        if not hs:
            continue
        last = max(os.path.getmtime(os.path.join(hdir, h)) for h in hs)
        rows.append({"feature": name, "artifact_versions": len(hs),
                     "last_touched": time.strftime("%Y-%m-%d", time.localtime(last))})
    rows.sort(key=lambda r: r["artifact_versions"], reverse=True)
    return rows


def _med(xs):
    return round(statistics.median(xs), 1) if xs else None


def compute(start_dir, window_days=90):
    result = dae_resolve.resolve(start_dir)
    root = result["methodology_root"] if result else os.path.abspath(start_dir)
    since = time.time() - window_days * DAY

    deploys = _deploys(root, since)
    lead = _feature_lead_times(root)
    fixes_in_window, mttr = _fix_stats(root, since)
    weeks = max(window_days / 7.0, 1)

    return {
        "project": os.path.basename(root.rstrip("/")) or "project",
        "window_days": window_days,
        "dora": {
            "deploy_frequency": {
                "count": len(deploys),
                "per_week": round(len(deploys) / weeks, 2),
            },
            "lead_time_days": {"median": _med(lead), "n": len(lead)},
            "change_failure_rate": {
                "rate": round(fixes_in_window / len(deploys), 2) if deploys else None,
                "fixes": fixes_in_window, "deploys": len(deploys),
            },
            "mttr_days": {"median": _med(mttr), "n": len(mttr)},
        },
        "governance": _governance(root),
    }


def main(argv):
    args = list(argv)
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    as_json = "--json" in args
    if as_json:
        args.remove("--json")
    window = 90
    if "--window" in args:
        i = args.index("--window")
        try:
            window = int(args[i + 1])
        except (IndexError, ValueError):
            sys.stderr.write("--window needs an integer\n")
            return 3
        del args[i:i + 2]
    start_dir = args[0] if args else os.getcwd()
    data = compute(start_dir, window)
    if as_json:
        json.dump(data, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    d = data["dora"]
    sys.stdout.write("DORA · %s · last %dd\n" % (data["project"], data["window_days"]))
    sys.stdout.write("  deploy frequency : %s (%s/week)\n"
                     % (d["deploy_frequency"]["count"], d["deploy_frequency"]["per_week"]))
    sys.stdout.write("  lead time (med)  : %s days (n=%s)\n"
                     % (d["lead_time_days"]["median"], d["lead_time_days"]["n"]))
    sys.stdout.write("  change fail rate : %s (%s fixes / %s deploys)\n"
                     % (d["change_failure_rate"]["rate"], d["change_failure_rate"]["fixes"],
                        d["change_failure_rate"]["deploys"]))
    sys.stdout.write("  MTTR (med)       : %s days (n=%s)\n"
                     % (d["mttr_days"]["median"], d["mttr_days"]["n"]))
    sys.stdout.write("  governance rows  : %d features with handoffs\n" % len(data["governance"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
